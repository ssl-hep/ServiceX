# Copyright (c) 2022, IRIS-HEP
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

from celery import Celery

app = Celery(broker="amqp://user:leftfoot1@localhost:5672")
app.conf.task_routes = {
    'transformer-123-456.transform_file': {'queue': '123-456'}
}

routes = app.conf.task_routes
routes['transformer-654-321.transform_file'] = {'queue': '654-321'}
app.conf.task_routes = routes
print(app.conf.task_routes)
task_id = app.send_task('transformer-123-456.transform_file',
                        kwargs={'request_id': 'c71584e9-077a-4cc0-832a-64b501cd20cc',
                                'file_id': 271,
                                'paths': 'root://fax.mwt2.org:1094//pnfs/uchicago.edu/atlaslocalgroupdisk/rucio/user/mtost/17/e2/user.mtost.39696075._000004.newer_TCPT_version.root', 'service_endpoint': 'http://host.docker.internal:5000/servicex/internal/transformation/c71584e9-077a-4cc0-832a-64b501cd20cc',  # NOQA E501
                                'result_destination': 'object-store',
                                'result_format': 'root-file'})
print(task_id)
