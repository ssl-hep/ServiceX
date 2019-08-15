import json

import time

from flask import Flask
from flask_restful import Api
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
import pika
from threading import Thread
from kafka_topic_manager import create_topic

app = Flask(__name__)

api = Api(app)

app.config.from_envvar('APP_CONFIG_FILE')

db = SQLAlchemy(app)
jwt = JWTManager(app)


import resources, servicex_resources


def callback(channel, method, properties, body):
    validated_request = json.loads(body)
    create_topic(validated_request['request_id'],
                 validated_request['info']['max_event_size'], 100)
    print(validated_request)
    print("Launch job against request_id "+ validated_request['request_id'])
    # launch_transformer_jobs()


def job_starting_thread():
    _rabbitmq = pika.BlockingConnection(
        pika.ConnectionParameters(app.config['RABBIT_MQ_URL']))
    _channel = _rabbitmq.channel()

    _channel.basic_consume(queue="validated_requests",
                           auto_ack=False,
                           on_message_callback=callback)
    _channel.start_consuming()


thread = Thread(target=job_starting_thread)
thread.daemon = True
thread.start()


@app.before_first_request
def create_tables():
    db.create_all()


api.add_resource(resources.UserRegistration, '/registration')
api.add_resource(resources.UserLogin, '/login')
api.add_resource(resources.UserLogoutAccess, '/logout/access')
api.add_resource(resources.UserLogoutRefresh, '/logout/refresh')
api.add_resource(resources.TokenRefresh, '/token/refresh')
api.add_resource(resources.AllUsers, '/users')
api.add_resource(resources.SecretResource, '/secret')

api.add_resource(servicex_resources.SubmitTransformationRequest, '/servicex/transformation')
api.add_resource(servicex_resources.QueryTransformationRequest,
                 '/servicex/transformation/<string:request_id>',
                 '/servicex/transformation')
api.add_resource(servicex_resources.TransformationStatus,
                 '/servicex/transformation/<string:request_id>/status')


