import json

import time

from flask import Flask
from flask_restful import Api
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager

import transformer_manager

app = Flask(__name__)

api = Api(app)

app.config.from_envvar('APP_CONFIG_FILE')

db = SQLAlchemy(app)
jwt = JWTManager(app)

if app.config['TRANSFORMER_MANAGER_ENABLED']:
    transformer_manager.config(app.config['TRANSFORMER_MANAGER_MODE'])

import resources, servicex_resources

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

api.add_resource(servicex_resources.AddFileToDataset,
                 '/servicex/transformation/<string:request_id>/files')

api.add_resource(servicex_resources.PreflightCheck,
                 '/servicex/transformation/<string:request_id>/preflight')

api.add_resource(servicex_resources.FilesetComplete,
                 '/servicex/transformation/<string:request_id>/complete')

api.add_resource(servicex_resources.TransformStart,
                 '/servicex/transformation/<string:request_id>/start')
