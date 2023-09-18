"""
Definition for abstract Object storage manager class
"""


# Copyright (c) 2019, IRIS-HEP
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import abc
import pathlib
from typing import List
from typing import Tuple


class ObjectStore(abc.ABC):
    """
    Abstract class for object storage managers to use
    """
    @abc.abstractmethod
    def get_storage_used(self) -> int:
        """
        Get storage used by object store
        :return: total storage used in bytes
        """

    @abc.abstractmethod
    def upload_file(self, bucket: str, object_name: str, path: pathlib.Path) -> None:
        """
        Save file to object store
        :param bucket: name of bucket
        :param object_name: name of object
        :param path: path to source file
        :return: None
        """

    @abc.abstractmethod
    def cleanup_storage(self,
                        max_size: int, norm_size: int, max_age: int) -> Tuple[int, List[str]]:
        """
        Reduce storage used until it's less than max_size
        :param max_size: Maximum amount of storage to use before trying to clean up
        :param norm_size: when this size is achieved, stop removing files
        :param max_age: Maximum number of days a bucket can be before it is cleaned up
        :return: Tuple with final storage used and list of buckets removed
        """

    @abc.abstractmethod
    def delete_object(self, bucket: str, object_name: str) -> None:
        """
        Delete object from store
        :param bucket: name of bucket
        :param object_name: name of object
        :return: None
        """

    @abc.abstractmethod
    def delete_objects(self, bucket: str, object_names: List[str]) -> List[Tuple[str, str]]:
        """
        Delete object from store
        :param bucket: name of bucket
        :param object_names: name of object
        :return: List of booleans indicating whether each corresponding object was deleted
        """

    @abc.abstractmethod
    def get_file(self, bucket: str, object_name: str, path: pathlib.Path) -> None:
        """
        Get an object from store
        :param bucket: name of bucket
        :param object_name: name of object
        :param path: path to destination file (must not be present)
        :return: None
        """

    @abc.abstractmethod
    def get_buckets(self) -> List[str]:
        """
        Get an list of buckets from store
        :return: List of buckets
        """

    @abc.abstractmethod
    def create_bucket(self, bucket: str) -> bool:
        """
        Create a bucket with given id
        :return: True on success, False otherwise
        """

    @abc.abstractmethod
    def delete_bucket(self, bucket: str) -> bool:
        """
        Get delete bucket from store
        :return: True on success, False otherwise
        """
