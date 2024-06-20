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
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pytest import fixture

from servicex_models import Base
from servicex_models.dataset import Dataset, DatasetStatus, DatasetFile


@fixture
def session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)

def test_dataset_insert(session):
    with session() as session:
        dataset = Dataset(
            name='foo',
            last_used=datetime(2022, 1, 1),
            last_updated=datetime(2022, 6, 5),
            did_finder="rucio",
            n_files=42,
            size=44,
            events=100,
            lookup_status='created'
        )
        session.add(dataset)
        session.commit()
        assert session.query(Dataset).count() == 1
        validate = Dataset.find_by_name(session, "foo")
        print(f"ID = {validate.id}")
        assert validate.name == 'foo'
        assert validate.last_used == datetime(2022, 1, 1)
        assert validate.last_updated == datetime(2022, 6, 5)
        assert validate.did_finder == "rucio"
        assert validate.n_files == 42
        assert validate.size == 44
        assert validate.events == 100
        assert validate.lookup_status == DatasetStatus.created

        found = Dataset.find_by_id(session, validate.id)
        assert found.name == 'foo'

def test_dataset_files(session):
    # noinspection PyTypeChecker
    dataset = Dataset(
        name='foo',
        last_used=datetime(2022, 1, 1),
        last_updated=datetime(2022, 6, 5),
        did_finder="rucio",
        n_files=42,
        size=44,
        events=100,
        lookup_status='created',
        files = [
            DatasetFile(
                paths='file1.root',
                file_size=10,
                file_events=10
            ),
            DatasetFile(
                paths='file2.root',
                file_size=10,
                file_events=10
            )
        ]
    )

    with session() as session:
        session.add(dataset)
        session.commit()

        validate = Dataset.find_by_name(session, "foo")
        assert len(validate.files) == 2


