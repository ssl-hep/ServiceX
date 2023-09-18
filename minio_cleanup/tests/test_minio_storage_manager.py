import datetime
import unittest
from collections import namedtuple

from unittest.mock import patch

import servicex_storage.s3_storage_manager

ObjectInfo = namedtuple('ObjectInfo', ['size', 'last_modified'])
s3_fake_objects = {
    "bucket1": {
        "object1": ObjectInfo(size=10,
                              last_modified=datetime.datetime(year=2021, month=10, day=1, hour=10, minute=10, second=10)),
        "object2": ObjectInfo(size=20,
                              last_modified=datetime.datetime(year=2021, month=10, day=1, hour=10, minute=11, second=10)),
        "object3": ObjectInfo(size=30,
                              last_modified=datetime.datetime(year=2021, month=10, day=1, hour=10, minute=12, second=10)),
    },
    "bucket2": {
        "object4": ObjectInfo(size=100,
                              last_modified=datetime.datetime(year=2020, month=10, day=1, hour=10, minute=10, second=10)),
        "object5": ObjectInfo(size=200,
                              last_modified=datetime.datetime(year=2020, month=10, day=1, hour=10, minute=11, second=10)),
        "object6": ObjectInfo(size=300,
                              last_modified=datetime.datetime(year=2020, month=10, day=1, hour=10, minute=12, second=10)),
    }
}


class MyTestCase(unittest.TestCase):
    @patch('minio.Minio')
    def test_s3_get_bucket_info(self, mock_class):
        """
        Test s3's get bucket info
        :return: None
        """

        mock_class().list_objects.return_value = list(s3_fake_objects["bucket1"].keys())
        mock_class().stat_object.side_effect = list(s3_fake_objects["bucket1"].values())
        return_value = servicex_storage.s3_storage_manager.BucketInfo(name="bucket1",
                                                                      size=60,
                                                                      last_modified=datetime.datetime(
                                                                          year=2021, month=10,
                                                                          day=1, hour=10,
                                                                          minute=10, second=10))
        test_obj = servicex_storage.s3_storage_manager.S3Store(s3_endpoint="abc",
                                                               access_key="abc",
                                                               secret_key="abc")
        bucket_info = test_obj.get_bucket_info("bucket1")
        self.assertEqual(bucket_info, return_value)

    @patch('minio.Minio')
    def test_minio_get_storage_used(self, mock_class):
        """
        Test getting storage used by a s3 bucket
        :return: None
        """
        mock_class().list_buckets.return_value = list(s3_fake_objects.keys())
        mock_class().list_objects.side_effect = [list(s3_fake_objects["bucket1"].keys()),
                                                 list(s3_fake_objects["bucket2"].keys())]
        mock_class().stat_object.side_effect = list(s3_fake_objects["bucket1"].values()) + \
            list(s3_fake_objects["bucket2"].values())

        test_obj = servicex_storage.s3_storage_manager.S3Store(s3_endpoint="abc",
                                                               access_key="abc",
                                                               secret_key="abc")

        bucket_size = test_obj.get_storage_used()
        self.assertEqual(bucket_size, 660)

    @patch('minio.Minio')
    def test_s3_cleanup_storage(self, mock_class):
        """
        Test minio's get bucket info
        :return: None
        """
        current_s3_fake_objects = {
            "bucket1": {
                "object1": ObjectInfo(size=10,
                                      last_modified=datetime.datetime.utcnow()),
                "object2": ObjectInfo(size=20,
                                      last_modified=datetime.datetime.utcnow()),
                "object3": ObjectInfo(size=30,
                                      last_modified=datetime.datetime.utcnow()),
            },
            "bucket2": {
                "object4": ObjectInfo(size=100,
                                      last_modified=datetime.datetime(year=2020, month=10, day=1, hour=10, minute=10,
                                                                      second=10)),
                "object5": ObjectInfo(size=200,
                                      last_modified=datetime.datetime(year=2020, month=10, day=1, hour=10, minute=11,
                                                                      second=10)),
                "object6": ObjectInfo(size=300,
                                      last_modified=datetime.datetime(year=2020, month=10, day=1, hour=10, minute=12,
                                                                      second=10)),
            }
        }

        mock_class().list_buckets.return_value = list(current_s3_fake_objects.keys())
        mock_class().list_objects.side_effect = [list(current_s3_fake_objects["bucket1"].keys()),
                                                 list(current_s3_fake_objects["bucket2"].keys()),
                                                 list(current_s3_fake_objects["bucket2"].keys())]
        mock_class().stat_object.side_effect = list(current_s3_fake_objects["bucket1"].values()) + \
            list(current_s3_fake_objects["bucket2"].values())

        test_obj = servicex_storage.s3_storage_manager.S3Store(s3_endpoint="abc",
                                                               access_key="abc",
                                                               secret_key="abc")

        final_size = test_obj.cleanup_storage(70, 60, 365)[0]
        self.assertEqual(final_size, 60)
        mock_class().remove_objects.assert_called_with(
            "bucket2", ["object4", "object5", "object6"])


if __name__ == '__main__':
    unittest.main()
