# Copyright (c) 2022, IRIS-HEP
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
from typing import Optional

from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Text, ForeignKey
from sqlalchemy.orm import relationship, Session
from sqlalchemy import Enum as DBEnum

from servicex_models import Base


class DatasetStatus(Enum):
    created = "created"
    looking = "looking"
    complete = "complete"


class Dataset(Base):
    __tablename__ = 'datasets'

    id = Column(Integer, primary_key=True)
    name = Column(String(1024), unique=True, nullable=False, index=True)
    last_used = Column(DateTime, nullable=False)
    last_updated = Column(DateTime, nullable=True)
    did_finder = Column(String(64), nullable=False)
    n_files = Column(Integer, default=0, nullable=True)
    size = Column(BigInteger, default=0, nullable=True)
    events = Column(BigInteger, default=0, nullable=True)
    lookup_status = Column(DBEnum(DatasetStatus), nullable=False)
    files = relationship("DatasetFile",
                         cascade='all,delete',
                         back_populates="dataset")

    def to_json(self):
        iso_fmt = '%Y-%m-%dT%H:%M:%S.%fZ'
        result_obj = {
            'id': self.id,
            'name': self.name,
            'did_finder': self.did_finder,
            'n_files': self.n_files,
            'size': self.size,
            'events': self.events,
            'last_used': str(self.last_used.strftime(iso_fmt)),
            'last_updated': str(self.last_updated.strftime(iso_fmt)),
            'lookup_status': self.lookup_status
        }
        return result_obj

    @classmethod
    def find_by_name(cls, session:Session, name:str) -> Optional['Dataset']:
        return session.query(Dataset).filter_by(name=name).first()

    @classmethod
    def find_by_id(cls, session:Session, id_to_find:int) -> Optional['Dataset']:
        return session.query(Dataset).get(id_to_find)


class DatasetFile(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer,
                           ForeignKey('datasets.id'),
                           nullable=False)
    adler32 = Column(String(48), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    file_events = Column(BigInteger, nullable=True)
    paths = Column(Text(), unique=False, nullable=False)
    dataset = relationship("Dataset", back_populates="files")


    @classmethod
    def get_by_id(cls, dataset_file_id):
        return cls.query.filter_by(id=dataset_file_id).one()
