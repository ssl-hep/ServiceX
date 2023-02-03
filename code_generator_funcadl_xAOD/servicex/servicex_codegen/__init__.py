#  Copyright (c) 2022 , IRIS-HEP
#   All rights reserved.
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice, this
#     list of conditions and the following disclaimer.
#
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#
#   * Neither the name of the copyright holder nor the names of its
#     contributors may be used to endorse or promote products derived from
#     this software without specific prior written permission.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#   AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#   IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#   DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#   FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#   DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#   SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#   CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#   OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#   OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
import os
import logging

from flask import Flask, jsonify
from flask_restful import Api

from servicex_codegen.post_operation import GeneratedCode


def handle_invalid_usage(error: BaseException):
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

    level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    app.logger.level = getattr(logging, level, None)

    if test_config:
        app.config.from_mapping(test_config)
    else:
        if 'CODEGEN_CONFIG_FILE' in os.environ:
            app.logger.info(os.environ.get('TRANSFORMER_SCIENCE_IMAGE'))
            app.config.from_envvar('CODEGEN_CONFIG_FILE')

    with app.app_context():
        translator = provided_translator

        api = Api(app)
        GeneratedCode.make_api(translator)

        api.add_resource(GeneratedCode, '/servicex/generated-code')

    app.errorhandler(Exception)(handle_invalid_usage)

    return app
