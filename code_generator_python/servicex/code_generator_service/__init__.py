import os

from flask import Flask
from flask_restful import Api
from servicex.code_generator_service.generate_code import GenerateCode
from servicex.code_generator_service.python_translator import PythonTranslator


def handle_invalid_usage(error: BaseException):
    from flask import jsonify
    response = jsonify({"message": str(error)})
    response.status_code = 400
    return response


def create_app(test_config=None, provided_translator=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    if not test_config:
        app.config.from_envvar('APP_CONFIG_FILE')
    else:
        app.config.from_mapping(test_config)

    with app.app_context():

        if not provided_translator:
            translator = PythonTranslator()
        else:
            translator = provided_translator

        api = Api(app)
        GenerateCode.make_api(translator)

        api.add_resource(GenerateCode, '/servicex/generated-code')

    app.errorhandler(Exception)(handle_invalid_usage)

    return app
