import datetime
import logging
import os
import boto3
import boto3.session
from botocore.client import ClientError
import psycopg2

max_bucket_age = int(os.environ.get('MAX_S3_AGE', '30'))
max_request_age = int(os.environ.get('MAX_REQUEST_AGE', '30'))
max_did_age = int(os.environ.get('MAX_DID_LOOKUP_AGE', '7'))
db_uri = os.environ.get('DATABASE_URI')


def toTiB(nbytes):
    return float(nbytes)/1024/1024/1024/1024


def toGiB(nbytes):
    return float(nbytes)/1024/1024/1024


class BucketInfo():
    def __init__(self, name, request_created, status):
        self.name = name
        self.last_modified = request_created
        self.size = 0
        self.objects = 0
        self.to_delete = False
        self.deleted = False
        self.present = False
        self.status = status

    def __str__(self) -> str:
        return f"name:{self.name} toDelete:{self.to_delete} deleted:{self.deleted} lm: {self.last_modified} size: {self.size} objects: {self.objects} status: {self.status}"


class S3Store():

    def __init__(self,
                 s3_endpoint: str, access_key: str, secret_key: str, use_https: bool = False):

        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())

        self.s3_endpoint = s3_endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.use_https = use_https
        self.s3 = boto3.client(
            service_name='s3',
            endpoint_url=self.s3_endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            verify=self.use_https
        )
        self.s3_resource = boto3.resource(
            's3',
            endpoint_url=self.s3_endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            verify=self.use_https
        )

    def get_bucket_info(self, bucket) -> BucketInfo:
        """
        Given a bucket, get the size and last modified date
        :param bucket: bucket name, bucket last modified
        """
        b = BucketInfo(bucket[0], bucket[1], bucket[2])
        try:
            response = self.s3.head_bucket(Bucket=b.name)
            # print(response)
            if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                b.present = True
                head = response['ResponseMetadata']['HTTPHeaders']
                b.size = int(head['x-rgw-bytes-used'])
                b.objects = int(head['x-rgw-object-count'])
        except ClientError:
            pass
            # print(f"no such bucket {b.name}")

        if not b.present:
            return

        bucket_age = datetime.datetime.now(
            datetime.timezone.utc) - b.last_modified.replace(tzinfo=datetime.timezone.utc)
        # marking empty buckets for deletion
        if b.size == 0 and bucket_age.days*86400 + bucket_age.seconds >= 7200:
            b.to_delete = True
        # marking old buckets for deletion
        if bucket_age.days > max_bucket_age:
            b.to_delete = True
        # marking buckets from canceled requests for deletion
        if b.status == 'canceled':
            b.to_delete = True

        print(b)
        return b

    def delete_bucket(self, bi: BucketInfo):
        """
        Delete a given bucket and contents
        """
        self.logger.info("deleting bucket", extra={"requestId": bi.name})
        bucket = self.s3_resource.Bucket(bi.name)
        for s3_object in bucket.objects.all():
            s3_object.delete()
        bucket.delete()
        bi.deleted = True

    def bi_sums(self, bil, message):
        total_buckets = 0
        total_objects = 0
        total_size = 0
        for bi in bil:
            total_buckets += 1
            total_size += bi.size
            total_objects += bi.objects
        self.logger.info(message, extra={
            "buckets": total_buckets,
            "objects": total_objects,
            "size": total_size
        })
        return total_size

    def get_servicex_requests(self):
        requests = []
        try:
            # Establish a connection to the database
            conn = psycopg2.connect(db_uri)
            cursor = conn.cursor()
            cursor.execute("SELECT request_id, submit_time, status FROM requests")
            rows = cursor.fetchall()
            for row in rows:
                # print(row)
                requests.append([row[0], row[1], row[2]])
            cursor.close()
            conn.close()

        except psycopg2.Error as e:
            print(f"Error connecting to the database: {e}")
        return requests

    def cleanup_storage(self, hwm: int, lwm: int):
        """
        Clean up storage by removing old files until below max_size
        :param hwm: max amount of storage that can be used before trying to clean up
        :param lwm: when this size is achieved, stop removing files
        """

        # get all the requests known to ServiceX
        buckets = self.get_servicex_requests()

        self.logger.info('request in servicex db', extra={"requests": len(buckets)})

        buckets_info = []
        for b in buckets:
            bi = self.get_bucket_info(b)
            if bi:
                buckets_info.append(bi)

        total_size = self.bi_sums(buckets_info, "before old cleanup.")

        buckets_info.sort(key=lambda x: x.last_modified)

        new_buckets_info = []
        for bi in buckets_info:
            if bi.to_delete:
                self.delete_bucket(bi)
            else:
                new_buckets_info.append(bi)

        total_size = self.bi_sums(new_buckets_info, "after old cleanup.")

        # marking for deletion in order to get to LWM
        if total_size < hwm:
            print('not above HWM')
        else:
            extra_space_needed = total_size-lwm
            print(f"above HWM. need to free: {extra_space_needed} bytes.")
            for bi in new_buckets_info:
                if extra_space_needed < 0:
                    break
                bi.to_delete = True
                extra_space_needed -= bi.size

            buckets_info = []
            for bi in new_buckets_info:
                if bi.to_delete:
                    self.delete_bucket(bi)
                else:
                    buckets_info.append(bi)

            total_size = self.bi_sums(buckets_info, "after size cleanup.")
