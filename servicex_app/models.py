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
from sqlalchemy import func

from run import db
from passlib.hash import pbkdf2_sha256 as sha256


class TransformRequest(db.Model):
    __tablename__ = 'requests'

    @classmethod
    def to_json(cls, x):
        return {
            'request_id': x.request_id,
            'did': x.did,
            'columns': x.columns,
            'image': x.image,
            'chunk-size': x.chunk_size,
            'workers': x.workers,
            'messaging-backend': x.messaging_backend,
            'kafka-broker': x.kafka_broker
        }

    id = db.Column(db.Integer, primary_key=True)
    did = db.Column(db.String(120), unique=False, nullable=False)
    columns = db.Column(db.String(1024), unique=False, nullable=False)
    request_id = db.Column(db.String(48), unique=True, nullable=False)
    image = db.Column(db.String(128), nullable=True)
    chunk_size = db.Column(db.Integer, nullable=True)
    workers = db.Column(db.Integer, nullable=True)
    messaging_backend = db.Column(db.String(32), nullable=True)
    kafka_broker = db.Column(db.String(128), nullable=True)

    files = db.Column(db.Integer, nullable=True)
    files_skipped = db.Column(db.Integer, nullable=True)
    total_events = db.Column(db.Integer, nullable=True)
    total_bytes = db.Column(db.Integer, nullable=True)
    did_lookup_time = db.Column(db.Integer, nullable=True)

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    @classmethod
    def return_all(cls):
        return {'requests': list(map(lambda x: cls.to_json(x),
                                     TransformRequest.query.all()))}

    @classmethod
    def return_request(cls, request_id):
        return cls.query.filter_by(request_id=request_id).one()

    @classmethod
    def update_request(cls, request_obj):
        db.session.commit()


class TransformationResult(db.Model):
    __tablename__ = 'transform_result'

    id = db.Column(db.Integer, primary_key=True)
    did = db.Column(db.String(120), unique=False, nullable=False)
    file_path = db.Column(db.String(120), unique=False, nullable=False)
    request_id = db.Column(db.String(48), unique=False, nullable=False)
    transform_status = db.Column(db.String(10), nullable=False)
    transform_time = db.Column(db.Integer, nullable=True)
    messages = db.Column(db.Integer, nullable=True)

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    @classmethod
    def count(cls, request_id):
        return cls.query.filter_by(request_id=request_id).count()

    @classmethod
    def statistics(cls, request_id):
        rslt = cls.query.add_columns(
            func.sum(TransformationResult.messages).label('total_msgs'),
            func.min(TransformationResult.transform_time).label('min_time'),
            func.max(TransformationResult.transform_time).label('max_time'),
            func.avg(TransformationResult.transform_time).label('avg_time')
        ).filter_by(request_id=request_id).one()

        return {
            "total-messages": rslt.total_msgs,
            "min-time": rslt.min_time,
            "max-time": rslt.max_time,
            "avg-time": rslt.avg_time
        }


class UserModel(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    @staticmethod
    def generate_hash(password):
        return sha256.hash(password)


    @staticmethod
    def verify_hash(password, hash):
        return sha256.verify(password, hash)


    @classmethod
    def find_by_username(cls, username):
        return cls.query.filter_by(username=username).first()

    @classmethod
    def return_all(cls):
        def to_json(x):
            return {
                'username': x.username,
                'password': x.password
            }

        return {'users': list(map(lambda x: to_json(x), UserModel.query.all()))}

    @classmethod
    def delete_all(cls):
        try:
            num_rows_deleted = db.session.query(cls).delete()
            db.session.commit()
            return {'message': '{} row(s) deleted'.format(num_rows_deleted)}
        except:
            return {'message': 'Something went wrong'}

