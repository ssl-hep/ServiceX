"""
Implementation of storage manager for minio based storage
"""

import datetime
import logging
import os
import pathlib
import concurrent.futures
import typing
from typing import List
from typing import Tuple
from collections import namedtuple

import minio
from minio.deleteobjects import DeleteObject

from servicex_storage import object_storage_manager

BucketInfo = namedtuple('BucketInfo', ['name', 'size', 'last_modified'])


class S3Store(object_storage_manager.ObjectStore):
  """
  Class to handle operations for minio storage
  """

  def __init__(self, s3_endpoint: str, access_key: str, secret_key: str, use_https: bool = False):
    super().__init__()

    self.logger = logging.getLogger(__name__)
    self.logger.addHandler(logging.NullHandler())

    self.s3_endpoint = s3_endpoint
    self.access_key = access_key
    self.secret_key = secret_key

    # s3 client is thread safe using Threading, not so much with multiprocessing
    self.__s3_client = minio.Minio(self.s3_endpoint,
                                   access_key=self.access_key,
                                   secret_key=self.secret_key,
                                   secure=use_https)

    # set up threads to use
    if "THREADS" in os.environ:
      try:
        self.__threads = int(os.environ["THREADS"])
        self.logger.debug("Using %d threads for storage cleanup", self.__threads)
      except ValueError:
        self.logger.exception("THREADS env variable not a number, using a single thread")
        self.__threads = 1
    else:
      self.__threads = 1

  def get_bucket_info(self, bucket: str) -> BucketInfo:
    """
    Given a bucket, get the size and last modified date
    :param bucket: bucket name
    :return: None
    """

    objects = self.__s3_client.list_objects(bucket)
    size = 0
    last_modified = datetime.datetime.now(datetime.timezone.utc)
    for obj in objects:
      if obj.object_name[-1] == '/':
        # this is a bucket within a bucket, skip because this isn't generated
        # by ServiceX
        continue
      result = self.__s3_client.stat_object(obj.bucket_name, obj.object_name)
      size += result.size
      if result.last_modified < last_modified:
        last_modified = result.last_modified
    return BucketInfo(name=bucket, size=size, last_modified=last_modified)

  def delete_bucket(self, bucket: str) -> bool:
    """
    Delete a given bucket and contents from minio
    :param bucket: bucket name
    :return:  None
    """
    if not self.__s3_client.bucket_exists(bucket):
      return True
    delete_objects = map(lambda x: DeleteObject(x.object_name), self.__s3_client.list_objects(bucket))
    errors = 0
    for error in self.__s3_client.remove_objects(bucket, delete_objects):
      errors += 1
    if errors != 0:
      return False
    self.__s3_client.remove_bucket(bucket)
    return True

  def get_storage_used(self) -> int:
    """
    Get the number of bytes used

    :return: integer with number of bytes used
    """
    buckets = self.__s3_client.list_buckets()
    if len(buckets) == 0:
      return 0

    # must use ThreadPool since minio client is thread safe with threading only
    with concurrent.futures.ThreadPoolExecutor(max_workers=self.__threads) as executor:
      sizes = executor.map(lambda x: self.get_bucket_info(x).size, buckets)
    total_size = sum(sizes)
    return total_size

  def delete_object(self, bucket: str, object_name: str) -> None:
    """
    Remove object from minio storage
    :param bucket:  name of bucket
    :param object_name:  name of object
    :return: None
    """
    self.__s3_client.remove_object(bucket, object_name)

  def delete_objects(self, bucket: str, object_names: List[str]) -> List[Tuple[str, str]]:
    """
    Delete object from store
    :param bucket: name of bucket
    :param object_names: name of object
    :return: List of tuples (objectName, error_message)
    """
    delete_objects = [DeleteObject(x) for x in object_names]
    delete_results = self.__s3_client.remove_objects(bucket, delete_objects)
    return [(x.name, x.message) for x in delete_results]

  def get_file(self, bucket: str, object_name: str, path: pathlib.Path) -> None:
    """
    Get object from minio and save to given path
    :param bucket: bucket name
    :param object_name: object name
    :param path: path to save
    :return: None
    """
    try:
      resp = self.__s3_client.fget_object(bucket, object_name, path)
    except Exception:  # pylint: disable=broad-except
      self.logger.exception("Got an exception while getting object")
    finally:
      resp.close()  # pylint: disable=no-member
      resp.release_conn()  # pylint: disable=no-member

  def upload_file(self, bucket: str, object_name: str, path: pathlib.Path) -> None:
    """
    Upload file to minio storage
    :param bucket: bucket name
    :param object_name: destination object name
    :param path: path of file source
    :return: None
    """
    if not os.path.isfile(path):
      mesg = f"Can't upload {path}: not present or not a file"
      self.logger.error(mesg)
      raise IOError(mesg)
    self.__s3_client.fput_object(bucket, object_name, path)

  def cleanup_storage(self, max_size: int, norm_size: int, max_age: int) -> Tuple[int, List[str]]:
    """
    Clean up storage by removing old files until below max_size
    :param max_size: max amount of storage that can be used before trying to clean up
    :param norm_size: when this size is achieved, stop removing files
    :param max_age: max number of days a bucket can be before it is deleted
    :return: Tuple with final size of storage used and list of buckets removed
    """
    buckets = map(lambda x: x.name, self.__s3_client.list_buckets())
    cleaned_buckets = []
    # must use ThreadPool since minio client is thread safe with threading only
    with concurrent.futures.ThreadPoolExecutor(max_workers=self.__threads) as executor:
      bucket_list = executor.map(self.get_bucket_info, buckets)

    # concurrently delete any old buckets
    with concurrent.futures.ThreadPoolExecutor(max_workers=self.__threads) as executor:
      kept_buckets = []
      old_buckets = []
      for bucket in bucket_list:
        bucket_age = (datetime.datetime.now(datetime.timezone.utc) - bucket.last_modified).days
        if bucket_age > max_age:
          old_buckets.append((bucket.name, bucket_age))
        else:
          kept_buckets.append(bucket)

      futures = {executor.submit(lambda x: self.delete_bucket(x), bucket[0]): (bucket[0], bucket[1])
                 for bucket in old_buckets}
      for future in concurrent.futures.as_completed(futures):
        bucket_info = futures[future]
        try:
          deleted = future.result()
          # use mesg in both log outputs with different capitalizations of D
          mesg = f"eleting {bucket_info[0]} due to age: {bucket_info[1]} days"
          if deleted:
            self.logger.info("D%s", mesg)
            cleaned_buckets.append(bucket_info[0])
          else:
            self.logger.error("Error d%s", mesg)
        except Exception:  # pylint: disable=broad-except
          self.logger.exception("Received exception while deleting %s due to age", bucket_info[0])

    kept_buckets.sort(key=lambda x: x.last_modified)
    idx = 0
    current_size = sum(map(lambda x: x.size, kept_buckets))
    if current_size > max_size:
      while current_size > norm_size and idx < len(kept_buckets):
        bucket = kept_buckets[idx]
        self.logger.info("Deleting %s due to storage limits", bucket.name)
        self.delete_bucket(bucket.name)
        cleaned_buckets.append(bucket.name)
        current_size -= bucket.size
        idx += 1
    return current_size, cleaned_buckets

  def get_buckets(self) -> List[str]:
    """
    Get list of buckets in s3
    :return: list of bucket names
    """
    return [x.name for x in self.__s3_client.list_buckets()]

  def create_bucket(self, bucket: str) -> bool:
    """
    Create a bucket with given id
    :return: None
    """
    try:
      self.__s3_client.make_bucket(bucket)
      return True
    except:
      return False

