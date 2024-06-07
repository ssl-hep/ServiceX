import logging
import os
import psycopg2
from typing import List
import datetime

max_request_age = int(os.environ.get('MAX_REQUEST_AGE', '30'))
max_did_age = int(os.environ.get('MAX_DID_LOOKUP_AGE', '6'))
db_uri = os.environ.get('DATABASE_URI')


class Req():
    def __init__(self, req_id, submit_time, status, did_id):
        self.req_id = req_id
        self.submit_time = submit_time
        self.status = status
        self.did_id = did_id

    def __str__(self) -> str:
        return f"req_id: {self.req_id} submit time: {self.submit_time} status:{self.status} did_id:{self.did_id}"


class DS():
    def __init__(self, id, last_used, last_updated, lookup_status):
        self.ds_id = id
        self.last_used = last_used
        self.last_updated = last_updated
        self.lookup_status = lookup_status

    def __str__(self) -> str:
        return f"ds_id:{self.ds_id} last used:{self.last_used} last updated:{self.last_updated} status:{self.lookup_status}"


class DBmanager():

    def __init__(self):

        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())
        self.conn = psycopg2.connect(db_uri)

    def get_servicex_requests(self) -> List[Req]:
        requests = []
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT request_id, submit_time, status, did_id FROM requests ORDER BY submit_time ASC"
            )
            rows = cursor.fetchall()
            for row in rows:
                # print(row)
                requests.append(Req(row[0], row[1], row[2], row[3]))
            cursor.close()

        except psycopg2.Error as e:
            print(f"Error geting requests: {e}")
        return requests

    def get_datasets(self) -> List[DS]:
        datasets = []
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT id, last_used, last_updated, lookup_status FROM datasets ORDER BY last_used ASC"
            )
            rows = cursor.fetchall()
            for row in rows:
                # print(row)
                datasets.append(DS(row[0], row[1], row[2], row[3]))
            cursor.close()

        except psycopg2.Error as e:
            print(f"Error geting requests: {e}")
        return datasets

    def delete_transform_results_req_id(self, req_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                f"delete from transform_result where request_id='{req_id}'"
            )
            self.conn.commit()
            cursor.close()
            self.logger.info(f'deleted transform_result related to {req_id}')

        except psycopg2.Error as e:
            print(f"Error deleting transform_result for req_id: {req_id}.\n{e}")
            self.conn.rollback()

    def delete_transform_results_file_id(self, file_id):
        pass

    def delete_request(self, req):

        # first remove transform_result
        self.delete_transform_results_req_id(req.req_id)

        try:
            cursor = self.conn.cursor()
            cursor.execute(
                f"delete from requests where request_id='{req.req_id}'"
            )
            self.conn.commit()
            cursor.close()
            self.logger.info(f'deleted request {req.req_id}')

        except psycopg2.Error as e:
            print(f"Error deleting request: {req.req_id},\n{e}")
            self.conn.rollback()

    def delete_files(self, dataset_id):
        pass

    def delete_dataset(self, ds):

        # first remove transform_result
        # self.delete_transform_results_req_id(req.req_id)

        try:
            cursor = self.conn.cursor()
            cursor.execute(
                f"delete from datasets where id='{ds.ds_id}'"
            )
            self.conn.commit()
            cursor.close()
            self.logger.info(f'deleted dataset {ds.ds_id}')

        except psycopg2.Error as e:
            # print(f"Error deleting dataset: {ds.ds_id}.\n{e}")
            self.conn.rollback()

    def cleanup_db(self):
        """
        Clean up db
        """

        # get all the requests known to ServiceX
        requests = self.get_servicex_requests()
        self.logger.info('request in servicex db', extra={"requests": len(requests)})

        # delete too old requests.
        for req in requests:
            req_age = datetime.datetime.now(
                datetime.timezone.utc) - req.submit_time.replace(tzinfo=datetime.timezone.utc)
            if req_age.days > max_request_age:
                self.delete_request(req)

        # get all the datasets in ServiceX
        datasets = self.get_datasets()
        self.logger.info('datasets in servicex db', extra={"datasets": len(datasets)})

        # delete datasets not used recently
        for ds in datasets:
            ds_age = datetime.datetime.now(
                datetime.timezone.utc) - ds.last_used.replace(tzinfo=datetime.timezone.utc)
            if ds_age.days > max_did_age:
                self.delete_dataset(ds)

        self.conn.close()
