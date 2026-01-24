# Copyright (c) 2025, IRIS-HEP
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
from datetime import datetime, timedelta, timezone

from flask import request, current_app

from servicex_app.resources.servicex_resource import ServiceXResource
from servicex_app.models import Dataset


class DatasetLifecycleOps(ServiceXResource):
    def post(self):
        """
        Obsolete cached datasets older than N hours
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            age = float(request.get_json().get("age", 24))
        except Exception:
            return {"message": "Invalid age parameter"}, 422
        delta = timedelta(hours=age)
        datasets = (
            Dataset.get_all()
        )  # by default this will only give non-stale datasets
        todelete = [
            _.id for _ in datasets if _.last_updated and (now - _.last_updated) > delta
        ]
        current_app.logger.info(
            f"Obsoletion called for datasets older than {delta}. "
            f"Obsoleting {len(todelete)} datasets."
        )
        for dataset_id in todelete:
            Dataset.delete_dataset(dataset_id)

        return {"message": "Success"}, 200
