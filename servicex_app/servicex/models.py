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
import hashlib
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, ForeignKey, DateTime
from sqlalchemy.orm.exc import NoResultFound

from servicex.mailgun_adaptor import MailgunAdaptor

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
    refresh_token = db.Column(db.Text, nullable=False, unique=True)
    sub = db.Column(db.String(120), nullable=False, unique=True, index=True)
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
    def find_by_email(cls, email) -> 'UserModel':
        return cls.query.filter_by(email=email).first()

    @classmethod
    def find_by_sub(cls, sub) -> 'UserModel':
        result = cls.query.filter_by(sub=sub).first()
        if result is None:
            raise NoResultFound(f"No user found matching subject: {sub}")
        return result

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
        try:
            num_rows_deleted = db.session.query(cls).delete()
            db.session.commit()
            return {'message': '{} row(s) deleted'.format(num_rows_deleted)}
        except Exception:
            return {'message': 'Something went wrong'}

    @classmethod
    def delete_all_pending(cls):
        try:
            num_rows_deleted = db.session.query.filter_by(pending=True).delete()
            db.session.commit()
            return {'message': '{} row(s) deleted'.format(num_rows_deleted)}
        except Exception:
            return {'message': 'Something went wrong'}

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


class TransformRequest(db.Model):
    __tablename__ = 'requests'
    OBJECT_STORE_DEST = 'object-store'
    KAFKA_DEST = 'kafka'

    _cache = {}

    @classmethod
    def to_json(cls, x):
        return {
            'request_id': x.request_id,
            'did': x.did,
            'columns': x.columns,
            'selection': x.selection,
            'tree-name': x.tree_name,
            'image': x.image,
            'chunk-size': x.chunk_size,
            'workers': x.workers,
            'result-destination': x.result_destination,
            'result-format': x.result_format,
            'kafka-broker': x.kafka_broker,
            'workflow-name': x.workflow_name,
            'generated-code-cm': x.generated_code_cm,
            'status': x.status,
            'failure-info': x.failure_description
        }

    id = db.Column(db.Integer, primary_key=True)
    submit_time = db.Column(db.DateTime, nullable=False)
    did = db.Column(db.String(512), unique=False, nullable=False)
    columns = db.Column(db.String(1024), unique=False, nullable=True)
    selection = db.Column(db.String(max_string_size), unique=False, nullable=True)
    tree_name = db.Column(db.String(512), unique=False, nullable=True)
    request_id = db.Column(db.String(48), unique=True, nullable=False)
    image = db.Column(db.String(128), nullable=True)
    chunk_size = db.Column(db.Integer, nullable=True)
    workers = db.Column(db.Integer, nullable=True)
    result_destination = db.Column(db.String(32), nullable=False)
    result_format = db.Column(db.String(32), nullable=False)
    kafka_broker = db.Column(db.String(128), nullable=True)
    workflow_name = db.Column(db.String(40), nullable=False)

    files = db.Column(db.Integer, nullable=True)
    files_skipped = db.Column(db.Integer, nullable=True)
    total_events = db.Column(db.BigInteger, nullable=True)
    total_bytes = db.Column(db.BigInteger, nullable=True)
    did_lookup_time = db.Column(db.Integer, nullable=True)
    generated_code_cm = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(128), nullable=True)
    failure_description = db.Column(db.String(max_string_size), nullable=True)

    def save_to_db(self):
        db.session.add(self)
        db.session.flush()

    @classmethod
    def return_all(cls):
        return {'requests': list(map(lambda x: cls.to_json(x),
                                     TransformRequest.query.all()))}

    @classmethod
    def get_request_cached(cls, request_id):
        if request_id in TransformRequest._cache:
            return TransformRequest._cache[request_id]

        live_val = TransformRequest.return_request(request_id)
        TransformRequest._cache[request_id] = live_val.id
        return live_val.id

    @classmethod
    def return_request(cls, request_id):
        try:
            return cls.query.filter_by(request_id=request_id).one()
        except NoResultFound:
            return None

    @classmethod
    def files_remaining(cls, request_id):
        submitted_request = cls.return_request(request_id)
        count = TransformationResult.count(request_id)

        if submitted_request and submitted_request.files:
            return submitted_request.files - int(count or 0)
        else:
            return None


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
    messages = db.Column(db.Integer, nullable=True)

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
            'avg-rate': x.avg_rate,
            'messages': x.messages
        }

    def save_to_db(self):
        db.session.add(self)
        db.session.flush()

    @classmethod
    def count(cls, request_id):
        return cls.query.filter_by(request_id=request_id).count()

    @classmethod
    def failed_files(cls, request_id):
        return cls.query.filter(TransformationResult.request_id == request_id,
                                TransformationResult.transform_status != 'success').count()

    @classmethod
    def get_all_status(cls, request_id):
        return cls.query.filter(TransformationResult.request_id == request_id).all()

    @classmethod
    def statistics(cls, request_key):
        rslt_list = db.session.query(
            TransformationResult.request_id,
            func.sum(TransformationResult.messages).label('total_msgs'),
            func.min(TransformationResult.transform_time).label('min_time'),
            func.max(TransformationResult.transform_time).label('max_time'),
            func.avg(TransformationResult.transform_time).label('avg_time'),
            func.sum(TransformationResult.transform_time).label('total_time'),
            func.avg(TransformationResult.avg_rate).label('avg_rate'),
            func.sum(TransformationResult.total_bytes).label('total_bytes'),
            func.sum(TransformationResult.total_events).label('total_events')
        ).group_by(TransformationResult.request_id).filter_by(
            request_id=request_key).all()

        if len(rslt_list) == 0:
            return None

        rslt = rslt_list[0]

        return {
            "total-messages": int(rslt.total_msgs),
            "min-time": int(rslt.min_time),
            "max-time": int(rslt.max_time),
            "avg-time": float(rslt.avg_time),
            "total-time": int(rslt.total_time),
            "avg-rate": float(rslt.avg_rate),
            "total-bytes": int(rslt.total_bytes),
            "total-events": int(rslt.total_events)
        }


class DatasetFile(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(48),
                           ForeignKey('requests.request_id'),
                           unique=False,
                           nullable=False)
    file_path = db.Column(db.String(512), unique=False, nullable=False)

    adler32 = db.Column(db.String(48), nullable=True)
    file_size = db.Column(db.BigInteger, nullable=True)
    file_events = db.Column(db.BigInteger, nullable=True)

    def save_to_db(self):
        db.session.add(self)
        db.session.flush()

    @classmethod
    def get_by_id(cls, dataset_file_id):
        return cls.query.filter_by(id=dataset_file_id).one()

    def get_path_id(self):
        return self.request_id+":"+str(self.id)


class FileStatus(db.Model):
    __tablename__ = 'file_status'

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, nullable=False)
    request_id = db.Column(db.String(48),
                           ForeignKey('requests.request_id'),
                           unique=False,
                           nullable=False)
    status = db.Column(db.String(128), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    pod_name = db.Column(db.String(128), nullable=True)

    info = db.Column(db.String(max_string_size), nullable=True)

    def save_to_db(self):
        db.session.add(self)
        db.session.flush()

    @classmethod
    def failures_for_request(cls, request_id):
        return db.session.query(DatasetFile, FileStatus).filter(
            FileStatus.request_id == request_id,
            DatasetFile.request_id == FileStatus.request_id,
            FileStatus.status == 'failure').all()
