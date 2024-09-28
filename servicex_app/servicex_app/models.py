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
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterable, List, Optional, Union

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from servicex_app.mailgun_adaptor import MailgunAdaptor

db = SQLAlchemy()
max_string_size = 10485760


class UserModel(db.Model):
    __tablename__ = 'users'
    admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    email = db.Column(db.String(320), nullable=False, unique=True)
    experiment = db.Column(db.String(120))
    id = db.Column(db.Integer, primary_key=True)
    institution = db.Column(db.String(120))
    name = db.Column(db.String(120), nullable=False)
    pending = db.Column(db.Boolean, default=True)
    refresh_token = db.Column(db.Text, nullable=True, unique=True)
    sub = db.Column(db.String(120), nullable=False, unique=True, index=True)
    requests = db.relationship('TransformRequest', backref='user')
    updated_at = db.Column(DateTime, default=datetime.utcnow)

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self):
        db.session.delete(self)
        db.session.commit()

    def send_email(self, template_path):
        MailgunAdaptor().send(self.email, template_path)

    @classmethod
    def find_by_email(cls, email) -> Optional['UserModel']:
        return cls.query.filter_by(email=email).first()

    @classmethod
    def update_refresh_token_by_email(cls, email, refresh_token, pending) -> Optional['UserModel']:
        db.session.query(UserModel). \
            filter(UserModel.email == email). \
            update({'refresh_token': refresh_token, 'pending': pending})
        db.session.commit()
        return {'message': '{}\'s refresh token updated'.format(email)}

    @classmethod
    def find_by_sub(cls, sub) -> Optional['UserModel']:
        return cls.query.filter_by(sub=sub).first()

    # Defined for convenience in testing, since query is difficult to mock.
    @classmethod
    def find_by_id(cls, user_id) -> Optional['UserModel']:
        return db.session.get(cls, user_id)
        # return cls.query.get(user_id)

    @classmethod
    def return_all(cls):
        def to_json(x):
            return {
                'email': x.email,
                'id': x.id,
                'admin': x.admin,
                'pending': x.pending
            }

        return {'users': list(map(lambda x: to_json(x), UserModel.query.all()))}

    @classmethod
    def return_all_pending(cls):
        def to_json(x):
            return {
                'email': x.email,
                'id': x.id,
                'admin': x.admin
            }

        return {'users': list(map(lambda x: to_json(x),
                                  UserModel.query.filter_by(pending=True)))}

    @classmethod
    def delete_all(cls):
        num_rows_deleted = db.session.query(cls).delete()
        db.session.commit()
        return {'message': '{} row(s) deleted'.format(num_rows_deleted)}

    @classmethod
    def delete_all_pending(cls):
        num_rows_deleted = db.session.query.filter_by(pending=True).delete()
        db.session.commit()
        return {'message': '{} row(s) deleted'.format(num_rows_deleted)}

    @classmethod
    def accept(cls, email):
        pending_user = UserModel.find_by_email(email)
        if not pending_user:
            raise NoResultFound(f"No user registered with email: {email}")
        pending_user.pending = False
        pending_user.save_to_db()
        pending_user.send_email('welcome.html')

    @staticmethod
    def generate_hash(password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_hash(provided_password, key):
        return UserModel.generate_hash(provided_password) == key


class TransformStatus(Enum):
    submitted = ("Submitted", False)
    pending_lookup = ("Pending Lookup", False)
    lookup = ("Lookup", False)
    running = ("Running", False)
    complete = ("Complete", True)
    fatal = ("Fatal", True)
    canceled = ("Canceled", True)

    def __init__(self, string_name, is_complete):
        self.string_name = string_name
        self.is_complete = is_complete


class TransformRequest(db.Model):
    __tablename__ = 'requests'
    OBJECT_STORE_DEST = 'object-store'
    VOLUME_DEST = 'volume'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(48), unique=True, nullable=False, index=True)
    title = db.Column(db.String(128), nullable=True)
    submit_time = db.Column(db.DateTime, nullable=False)
    finish_time = db.Column(db.DateTime, nullable=True)
    did = db.Column(db.String(512), unique=False, nullable=False)
    did_id = db.Column(db.Integer, unique=False, nullable=False)
    selection = db.Column(db.String(max_string_size), unique=False, nullable=True)
    tree_name = db.Column(db.String(512), unique=False, nullable=True)
    image = db.Column(db.String(128), nullable=True)
    workers = db.Column(db.Integer, nullable=True)
    result_destination = db.Column(db.String(32), nullable=False)
    result_format = db.Column(db.String(32), nullable=False)
    submitted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    files = db.Column(db.Integer, default=0, nullable=False)
    files_completed = db.Column(db.Integer, default=0, nullable=False)
    files_failed = db.Column(db.Integer, default=0, nullable=False)

    total_events = db.Column(db.BigInteger, nullable=True)
    total_bytes = db.Column(db.BigInteger, nullable=True)
    did_lookup_time = db.Column(db.Integer, nullable=True)
    generated_code_cm = db.Column(db.String(128), nullable=True)
    status = db.Column(db.Enum(TransformStatus), nullable=False)
    failure_description = db.Column(db.String(max_string_size), nullable=True)
    app_version = db.Column(db.String(64), nullable=True)
    code_gen_image = db.Column(db.String(256), nullable=True)
    transformer_language = db.Column(db.String(256), nullable=True)
    transformer_command = db.Column(db.String(256), nullable=True)

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def to_json(self):
        iso_fmt = '%Y-%m-%dT%H:%M:%S.%fZ'
        result_obj = {
            'request_id': self.request_id,
            'title': self.title,
            'did': self.did,
            'did_id': self.did_id,
            'selection': self.selection,
            'tree-name': self.tree_name,
            'image': self.image,
            'workers': self.workers,
            'result-destination': self.result_destination,
            'result-format': self.result_format,
            'generated-code-cm': self.generated_code_cm,
            'status': self.status.string_name,
            'failure-info': self.failure_description,
            'app-version': self.app_version,
            'code-gen-image': self.code_gen_image,
            'files': self.files,
            'files-completed': self.files_completed,
            'files-failed': self.files_failed,
            'files-remaining': self.files_remaining,
            'submit-time': str(self.submit_time.strftime(iso_fmt)),
            'finish-time': str(self.finish_time)
        }
        if self.finish_time is not None:
            result_obj['finish-time'] = str(self.finish_time.strftime(iso_fmt))
        return result_obj

    @classmethod
    def return_json(cls, requests: Iterable['TransformRequest']):
        return {'requests': [r.to_json() for r in requests]}

    @classmethod
    def lookup(cls, key: Union[str, int]) -> Optional['TransformRequest']:
        """
        Looks up a TransformRequest by its request_id (UUID) or integer ID.
        :param key: Lookup key. Must be an integer, UUID, or string representation of an integer.
        If key is a numeric string, e.g. '17', it will be treated as an integer ID.
        All other strings are assumed to be UUIDs (request_id).
        :return result: TransformRequest with the given key, or None if not found.
        """
        try:
            if isinstance(key, int) or key.isnumeric():
                return db.session.get(cls, key)
            else:
                return cls.query.filter_by(request_id=key).one()
        except NoResultFound:
            return None

    @classmethod
    def lookup_running_by_dataset_id(cls, dataset_id: int) -> list[TransformRequest]:
        """
        Looks up TransformRequests in "Lookup" state that needs the dataset
        given by its dataset_id.
        :param dataset
        _id: dataset id. Must be an integer.
        :return result: list of TransformRequests, or empty list if not found.
        """
        try:
            return db.session.query(cls).filter((cls.status == TransformStatus.lookup) &
                                                (cls.did_id == dataset_id)).all()
        except NoResultFound:
            return []

    @classmethod
    def lookup_pending_on_dataset(cls, dataset_id: int) -> list[TransformRequest]:
        """
        Looks up TransformRequests that have been pending resolving of the given
        dataset ID.
        :param dataset_id: dataset id. Must be an integer.
        :return result: list of TransformRequests, or empty list if not found.
        """
        try:
            return db.session.query(cls).filter((cls.status == TransformStatus.pending_lookup) &
                                                (cls.did_id == dataset_id)).all()
        except NoResultFound:
            return []

    @classmethod
    def file_transformed_successfully(cls, key: Union[str, int]) -> None:
        db.session.commit()
        req = cls.query.filter_by(request_id=key).one()
        req.files_completed = cls.files_completed + 1
        db.session.commit()

    @classmethod
    def file_transformed_unsuccessfully(cls, key: Union[str, int]) -> None:
        db.session.commit()
        req = cls.query.filter_by(request_id=key).one()
        req.files_failed = cls.files_failed + 1
        db.session.commit()

    @classmethod
    def add_a_file(cls, key) -> None:
        req = cls.query.filter_by(request_id=key).one()
        req.files = TransformRequest.files + 1
        db.session.commit()

    @property
    def age(self) -> timedelta:
        return datetime.utcnow() - self.submit_time

    @property
    def submitter_name(self):
        if self.submitted_by is None:
            return None
        elif self.user is None:
            return "[deleted]"
        return self.user.name

    @property
    def files_remaining(self) -> int:
        if self.files:
            return self.files - self.files_completed - self.files_failed
        else:
            return None

    @property
    def result_count(self) -> int:
        return self.files_completed + self.files_failed

    @property
    def results(self) -> List['TransformationResult']:
        return TransformationResult.query.filter_by(request_id=self.request_id).all()

    @property
    def all_files(self) -> List['DatasetFile']:
        return DatasetFile.query.filter_by(dataset_id=self.did_id).all()

    @property
    def statistics(self) -> Optional[dict]:
        rslt_list = db.session.query(
            TransformationResult.request_id,
            func.min(TransformationResult.transform_time).label('min_time'),
            func.max(TransformationResult.transform_time).label('max_time'),
            func.avg(TransformationResult.transform_time).label('avg_time'),
            func.sum(TransformationResult.transform_time).label('total_time'),
            func.avg(TransformationResult.avg_rate).label('avg_rate'),
            func.sum(TransformationResult.total_bytes).label('total_bytes'),
            func.sum(TransformationResult.total_events).label('total_events')
        ).group_by(TransformationResult.request_id).filter_by(
            request_id=self.request_id).all()

        if len(rslt_list) == 0:
            return None

        rslt = rslt_list[0]

        return {
            "min-time": int(rslt.min_time),
            "max-time": int(rslt.max_time),
            "avg-time": float(rslt.avg_time),
            "total-time": int(rslt.total_time),
            "avg-rate": float(rslt.avg_rate),
            "total-bytes": int(rslt.total_bytes),
            "total-events": int(rslt.total_events)
        }


class TransformationResult(db.Model):
    __tablename__ = 'transform_result'

    id = db.Column(db.Integer, primary_key=True)
    did = db.Column(db.String(512), unique=False, nullable=False)
    file_id = db.Column(db.Integer, ForeignKey('files.id'))
    file_path = db.Column(db.String(512), unique=False, nullable=False)
    request_id = db.Column(db.String(48), unique=False, nullable=False)
    transform_status = db.Column(db.String(120), nullable=False)
    transform_time = db.Column(db.Integer, nullable=True)
    total_events = db.Column(db.BigInteger, nullable=True)
    total_bytes = db.Column(db.BigInteger, nullable=True)
    avg_rate = db.Column(db.Float, nullable=True)

    @classmethod
    def to_json_list(cls, a_list):
        return [TransformationResult.to_json(msg) for msg in a_list]

    @classmethod
    def to_json(cls, x):
        return {
            'id': x.id,
            'request-id': x.request_id,
            'did': x.did,
            'file-id': x.id,
            'file-path': x.file_path,
            'transform_status': x.transform_status,
            'transform_time': x.transform_time,
            'total-events': x.total_events,
            'total-bytes': x.total_bytes,
            'avg-rate': x.avg_rate
        }

    def save_to_db(self):
        db.session.add(self)
        db.session.flush()


class DatasetStatus(Enum):
    created = "created"
    looking = "looking"
    complete = "complete"


class Dataset(db.Model):
    __tablename__ = 'datasets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1024), unique=True, nullable=False, index=True)
    last_used = db.Column(db.DateTime, nullable=False)
    last_updated = db.Column(db.DateTime, nullable=True)
    did_finder = db.Column(db.String(64), nullable=False)
    n_files = db.Column(db.Integer, default=0, nullable=True)
    size = db.Column(db.BigInteger, default=0, nullable=True)
    events = db.Column(db.BigInteger, default=0, nullable=True)
    lookup_status = db.Column(db.Enum(DatasetStatus), nullable=False)
    files = relationship("DatasetFile", back_populates="dataset")

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

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
    def find_by_name(cls, name) -> Optional['Dataset']:
        return cls.query.filter_by(name=name).first()

    @classmethod
    def find_by_id(cls, id) -> Optional['Dataset']:
        return cls.query.get(id)


class DatasetFile(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True)
    dataset_id = db.Column(db.Integer,
                           ForeignKey('datasets.id'),
                           unique=False,
                           nullable=False)
    adler32 = db.Column(db.String(48), nullable=True)
    file_size = db.Column(db.BigInteger, nullable=True)
    file_events = db.Column(db.BigInteger, nullable=True)
    paths = db.Column(db.Text(), unique=False, nullable=False)
    dataset = relationship("Dataset", back_populates="files")

    def save_to_db(self):
        db.session.add(self)
        db.session.flush()

    @classmethod
    def get_by_id(cls, dataset_file_id):
        return cls.query.filter_by(id=dataset_file_id).one()
