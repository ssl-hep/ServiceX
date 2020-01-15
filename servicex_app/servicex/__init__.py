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

import os
from flask import Flask
from flask_restful import Api

from servicex.code_gen_adapter import CodeGenAdapter
from servicex.elasticsearch_adaptor import ElasticSearchAdapter
from servicex.rabbit_adaptor import RabbitAdaptor
from servicex.routes import add_routes
from servicex.transformer_manager import TransformerManager
from servicex.object_store_manager import ObjectStoreManager


def _init_rabbit_mq(rabbitmq_url):
    rabbit_mq_adaptor = RabbitAdaptor(rabbitmq_url)
    rabbit_mq_adaptor.connect()

    # Insure the required queues and exchange exist in RabbitMQ broker
    rabbit_mq_adaptor.setup_queue('did_requests')
    rabbit_mq_adaptor.setup_queue('validation_requests')
    rabbit_mq_adaptor.setup_exchange('transformation_requests')
    rabbit_mq_adaptor.setup_exchange('transformation_failures')
    return rabbit_mq_adaptor


def create_app(test_config=None,
               provided_transformer_manager=None,
               provided_rabbit_adaptor=None,
               provided_object_store=None,
               provided_elasticsearch_adapter=None,
               provided_code_gen_service=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    if not test_config:
        app.config.from_envvar('APP_CONFIG_FILE')
    else:
        app.config.from_mapping(test_config)
        print("Transformer enabled: ", test_config['TRANSFORMER_MANAGER_ENABLED'])

    with app.app_context():

        if app.config['OBJECT_STORE_ENABLED']:
            if not provided_object_store:
                object_store = ObjectStoreManager(app.config['MINIO_URL'],
                                                  username=app.config['MINIO_ACCESS_KEY'],
                                                  password=app.config['MINIO_SECRET_KEY'])
            else:
                object_store = provided_object_store
        else:
            object_store = None

        if app.config['TRANSFORMER_MANAGER_ENABLED'] and not provided_transformer_manager:
            transformer_manager = TransformerManager(app.config['TRANSFORMER_MANAGER_MODE'])
        else:
            transformer_manager = provided_transformer_manager

        if not provided_rabbit_adaptor:
            rabbit_adaptor = _init_rabbit_mq(app.config['RABBIT_MQ_URL'])
        else:
            rabbit_adaptor = provided_rabbit_adaptor

        if not provided_code_gen_service:
            code_gen_service = CodeGenAdapter(
                app.config['CODE_GEN_SERVICE_URL'],
                transformer_manager)
        else:
            code_gen_service = provided_code_gen_service

        if 'ELASTIC_SEARCH_LOGGING_ENABLED' in app.config \
                and app.config['ELASTIC_SEARCH_LOGGING_ENABLED']\
                and not provided_elasticsearch_adapter:
            elasticsearch_adaptor = ElasticSearchAdapter(
                app.config['ES_HOST'],
                app.config['ES_PORT'],
                app.config['ES_USER'],
                app.config['ES_PASS']
            )
        else:
            elasticsearch_adaptor = provided_elasticsearch_adapter

        api = Api(app)

        # ensure the instance folder exists
        try:
            os.makedirs(app.instance_path)
        except OSError:
            pass

        @app.before_first_request
        def create_tables():
            from servicex.models import db
            db.init_app(app)
            db.create_all()

        add_routes(api, transformer_manager, rabbit_adaptor, object_store,
                   elasticsearch_adaptor, code_gen_service)

    return app
