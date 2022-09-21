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
import logging
from distutils.util import strtobool
import sys

import os

from flask import Flask
from flask_bootstrap import Bootstrap5
from flask_cors import CORS
from flask_jwt_extended import (JWTManager)
from flask_restful import Api

from servicex.code_gen_adapter import CodeGenAdapter
from servicex.docker_repo_adapter import DockerRepoAdapter
from servicex.lookup_result_processor import LookupResultProcessor
from servicex.object_store_manager import ObjectStoreManager
from servicex.rabbit_adaptor import RabbitAdaptor
from servicex.routes import add_routes
from servicex.transformer_manager import TransformerManager


class ServiceXFormatter(logging.Formatter):
    """
    Need a custom formatter to allow for logging with request ids that vary.
    Normally log messages are "level instance component request_id msg" and
    request_id gets set by initialize_logging but we need a handler that'll let
    us pass in the request id and have that embedded in the log message
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format record with request id if present, otherwise assume None

        :param record: LogRecord
        :return: formatted log message
        """

        if not hasattr(record, "requestId"):
            setattr(record, "requestId", None)
        return super().format(record)


def _override_config_with_environ(app):
    """
    Use app.config as a guide to configuration settings that can be overridden from env
    vars.
    """
    # Env vars will be strings. Convert boolean values
    def _convert_string(value):
        return value if value not in ["true", "false"] else strtobool(value)

    # Create a dictionary of environment vars that have keys that match keys from the
    # loaded config. These will override anything from the config file
    return {k: (lambda key, value: _convert_string(os.environ[k]))(k, v) for (k, v)
            in app.config.items()
            if k in os.environ}


def create_app(test_config=None,
               provided_transformer_manager=None,
               provided_rabbit_adaptor=None,
               provided_object_store=None,
               provided_code_gen_service=None,
               provided_lookup_result_processor=None,
               provided_docker_repo_adapter=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    Bootstrap5(app)
    CORS(app)

    JWTManager(app)

    # setup logging
    instance = os.environ.get('INSTANCE_NAME', 'Unknown')
    formatter = ServiceXFormatter('%(levelname)s ' +
                                  f"{instance} servicex_app " +
                                  '%(requestId)s %(message)s')
    servicex_handler = logging.StreamHandler()
    servicex_handler.setFormatter(formatter)
    if app.debug:
        servicex_handler.setLevel('DEBUG')
        app.logger.level = logging.DEBUG
    else:
        levels = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'WARN': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        level = os.environ.get('LOG_LEVEL', 'WARNING').upper()
        servicex_handler.setLevel(levels[level])
        app.logger.level = levels[level]

    # remove current handlers and add our own
    for h in app.logger.handlers:
        app.logger.removeHandler(h)
    app.logger.addHandler(servicex_handler)
    app.logger.info("Initialized logging")

    if not test_config:
        app.config.from_envvar('APP_CONFIG_FILE')
        app.config.update(_override_config_with_environ(app))
    else:
        app.config.from_mapping(test_config)
        app.logger.info(f"Transformer enabled: {test_config['TRANSFORMER_MANAGER_ENABLED']}")

    with app.app_context():
        # Validate did-finder scheme
        schemes = app.config['VALID_DID_SCHEMES']
        if app.config['DID_FINDER_DEFAULT_SCHEME'] not in schemes:
            raise ValueError(f"Default DID Finder Scheme not listed in {schemes}")

        if app.config['OBJECT_STORE_ENABLED']:
            if not provided_object_store:
                if 'MINIO_ENCRYPT' in app.config:
                    if isinstance(app.config['MINIO_ENCRYPT'], bool):
                        use_https = app.config['MINIO_ENCRYPT']
                    else:
                        use_https = strtobool(app.config['MINIO_ENCRYPT'])
                else:
                    use_https = False
                object_store = ObjectStoreManager(app.config['MINIO_URL'],
                                                  username=app.config['MINIO_ACCESS_KEY'],
                                                  password=app.config['MINIO_SECRET_KEY'],
                                                  use_https=use_https)
            else:
                object_store = provided_object_store
        else:
            object_store = None

        if app.config['TRANSFORMER_MANAGER_ENABLED'] and not provided_transformer_manager:
            transformer_manager = TransformerManager(app.config['TRANSFORMER_MANAGER_MODE'])
        else:
            transformer_manager = provided_transformer_manager

        if not provided_rabbit_adaptor:
            rabbit_adaptor = RabbitAdaptor(app.config['RABBIT_MQ_URL'])
        else:
            rabbit_adaptor = provided_rabbit_adaptor

        if not provided_code_gen_service:
            code_gen_service = CodeGenAdapter(
                app.config['CODE_GEN_SERVICE_URL'],
                transformer_manager)
        else:
            code_gen_service = provided_code_gen_service

        if not provided_lookup_result_processor:
            lookup_result_processor = LookupResultProcessor(rabbit_adaptor,
                                                            "http://" +
                                                            app.config[
                                                                'ADVERTISED_HOSTNAME'] + "/"
                                                            )
        else:
            lookup_result_processor = provided_lookup_result_processor

        if not provided_docker_repo_adapter:
            docker_repo_adapter = DockerRepoAdapter()
        else:
            docker_repo_adapter = provided_docker_repo_adapter

        if transformer_manager and \
                'TRANSFORMER_PERSISTENCE_PROVIDED_CLAIM' in app.config and \
                app.config['TRANSFORMER_PERSISTENCE_PROVIDED_CLAIM'] and \
                not transformer_manager.persistent_volume_claim_exists(
                    app.config['TRANSFORMER_PERSISTENCE_PROVIDED_CLAIM'],
                    app.config['TRANSFORMER_NAMESPACE']):
            app.logger.error("Supplied Transformer Persistent Volume Claim Doesn't exist")
            sys.exit(-1)

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

        add_routes(api, transformer_manager, rabbit_adaptor, object_store, code_gen_service,
                   lookup_result_processor, docker_repo_adapter)

        # Inject useful Python modules to make them available in all templates
        @app.context_processor
        def inject_modules():
            import humanize
            import datetime
            return dict(datetime=datetime, humanize=humanize)

    return app
