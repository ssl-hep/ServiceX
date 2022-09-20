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
from flask import current_app

from servicex.decorators import auth_required
from servicex.models import TransformRequest, FileStatus
from servicex.resources.servicex_resource import ServiceXResource


class TransformErrors(ServiceXResource):
    @auth_required
    def get(self, request_id):
        """
        Fetches errors for a given transformation request.
        :param request_id: UUID of transformation request.
        """
        transform = TransformRequest.lookup(request_id)
        if not transform:
            msg = f'Transformation request not found with id: {request_id}'
            current_app.logger.error("When looking up errors, " + msg,
                                     extra={'requestId': request_id})
            return {'message': msg}, 404
        results = [{
            "pod-name": result[1].pod_name,
            "file": result[0].paths
            if isinstance(result[0].paths, str)
            else result[0].paths[0],
            "events": result[0].file_events,
            "info": result[1].info
        } for result in FileStatus.failures_for_request(request_id)]
        return {"errors": list(results)}
