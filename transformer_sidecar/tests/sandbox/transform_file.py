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
    "transformer-0ad80a11-c847-4874-90d6-6c0fc09bf854.transform_file": {
        "queue": "0ad80a11-c847-4874-90d6-6c0fc09bf854"
    }  # noqa 501
}

routes = app.conf.task_routes
routes["transformer-0ad80a11-c847-4874-90d6-6c0fc09bf854.transform_file"] = {
    "queue": "0ad80a11-c847-4874-90d6-6c0fc09bf854"
}  # noqa 501
app.conf.task_routes = routes
print(app.conf.task_routes)
task_id = app.send_task(
    "transformer-0ad80a11-c847-4874-90d6-6c0fc09bf854.transform_file",
    kwargs={
        "request_id": "0ad80a11-c847-4874-90d6-6c0fc09bf854",
        "service_endpoint": "http://localhost:5000",
        "file_id": 271,
        "paths": 'root://fax.mwt2.org:1094//pnfs/uchicago.edu/atlasdatadisk/rucio/mc20_13TeV/20/01/DAOD_PHYSLITE.37110983._000012.pool.root.1"',  # noqa 501
        "result_destination": "object-store",
        "result_format": "root-file",
    },
)
print(task_id)
