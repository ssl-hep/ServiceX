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
from flask import current_app as app


def add_routes(api, transformer_manager, rabbit_mq_adaptor,
               object_store, code_gen_service,
               lookup_result_processor, docker_repo_adapter):

    from servicex.resources.info import Info

    from servicex.resources.internal.add_file_to_dataset import AddFileToDataset
    from servicex.resources.internal.file_transform_status import FileTransformationStatus
    from servicex.resources.internal.fileset_complete import FilesetComplete
    from servicex.resources.internal.transform_start import TransformStart
    from servicex.resources.internal.transform_status import TransformationStatusInternal
    from servicex.resources.internal.transformer_file_complete import TransformerFileComplete

    from servicex.resources.transformation.submit import SubmitTransformationRequest
    from servicex.resources.transformation.status import TransformationStatus
    from servicex.resources.transformation.cancel import CancelTransform
    from servicex.resources.transformation.get_all import AllTransformationRequests
    from servicex.resources.transformation.get_one import TransformationRequest
    from servicex.resources.transformation.errors import TransformErrors
    from servicex.resources.transformation.deployment import DeploymentStatus

    from servicex.resources.users.all_users import AllUsers
    from servicex.resources.users.token_refresh import TokenRefresh
    from servicex.resources.users.accept_user import AcceptUser
    from servicex.resources.users.delete_user import DeleteUser
    from servicex.resources.users.pending_users import PendingUsers
    from servicex.resources.users.slack_interaction import SlackInteraction

    from servicex.web.home import home
    from servicex.web.about import about
    from servicex.web.sign_in import sign_in
    from servicex.web.sign_out import sign_out
    from servicex.web.auth_callback import auth_callback
    from servicex.web.user_dashboard import user_dashboard
    from servicex.web.global_dashboard import global_dashboard
    from servicex.web.view_profile import view_profile
    from servicex.web.edit_profile import edit_profile
    from servicex.web.api_token import api_token
    from servicex.web.servicex_file import servicex_file
    from servicex.web.transformation_request import transformation_request
    from servicex.web.transformation_results import transformation_results

    # Must be its own module to allow patching
    from servicex.web.create_profile import create_profile

    SubmitTransformationRequest.make_api(rabbitmq_adaptor=rabbit_mq_adaptor,
                                         object_store=object_store,
                                         code_gen_service=code_gen_service,
                                         lookup_result_processor=lookup_result_processor,
                                         docker_repo_adapter=docker_repo_adapter,
                                         transformer_manager=transformer_manager)

    # Web Frontend Routes
    app.add_url_rule('/', 'home', home)
    app.add_url_rule('/about', 'about', about)
    app.add_url_rule('/global-dashboard', 'global-dashboard', global_dashboard)
    app.add_url_rule('/sign-in', 'sign_in', sign_in)
    app.add_url_rule('/sign-out', 'sign_out', sign_out)
    app.add_url_rule('/auth-callback', 'auth_callback', auth_callback)
    app.add_url_rule('/api-token', 'api_token', api_token)
    app.add_url_rule('/.servicex', 'servicex-file', servicex_file)
    app.add_url_rule('/dashboard', 'user-dashboard', user_dashboard)
    app.add_url_rule('/profile', 'profile', view_profile)
    app.add_url_rule('/profile/new', 'create_profile', create_profile,
                     methods=['GET', 'POST'])
    app.add_url_rule('/profile/edit', 'edit_profile', edit_profile,
                     methods=['GET', 'POST'])
    app.add_url_rule(
        '/transformation-request/<id_>',
        'transformation_request',
        transformation_request
    )
    app.add_url_rule(
        '/transformation-request/<id_>/results',
        'transformation_results',
        transformation_results
    )

    # User management and Authentication Endpoints
    api.add_resource(TokenRefresh, '/token/refresh')
    api.add_resource(AllUsers, '/users')
    api.add_resource(AcceptUser, '/accept')
    api.add_resource(DeleteUser, '/users/<user_id>')
    api.add_resource(PendingUsers, '/pending')
    api.add_resource(SlackInteraction, '/slack')

    # Client public endpoints
    api.add_resource(Info, '/servicex')
    prefix = "/servicex/transformation"
    api.add_resource(SubmitTransformationRequest, prefix)
    api.add_resource(AllTransformationRequests, prefix)
    prefix += "/<string:request_id>"
    api.add_resource(TransformationRequest, prefix)
    api.add_resource(TransformationStatus, prefix + "/status")
    api.add_resource(TransformErrors, prefix + "/errors")
    api.add_resource(DeploymentStatus, prefix + "/deployment-status")
    api.add_resource(CancelTransform, prefix + "/cancel")

    # Internal service endpoints
    api.add_resource(TransformationStatusInternal,
                     '/servicex/internal/transformation/<string:request_id>/status')

    AddFileToDataset.make_api(lookup_result_processor)
    api.add_resource(AddFileToDataset,
                     '/servicex/internal/transformation/<string:request_id>/files')

    FilesetComplete.make_api(lookup_result_processor)
    api.add_resource(FilesetComplete,
                     '/servicex/internal/transformation/<string:request_id>/complete')

    TransformStart.make_api(transformer_manager)
    api.add_resource(TransformStart,
                     '/servicex/internal/transformation/<string:request_id>/start')

    api.add_resource(FileTransformationStatus,
                     '/servicex/internal/transformation/<string:request_id>/<int:file_id>/status')

    TransformerFileComplete.make_api(transformer_manager)
    api.add_resource(TransformerFileComplete,
                     '/servicex/internal/transformation/<string:request_id>/file-complete')
