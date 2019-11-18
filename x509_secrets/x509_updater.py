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
import sys
import time

import kubernetes
from kubernetes import client
import base64

secret_name = sys.argv[1]
print("Configuring "+secret_name)

kubernetes.config.load_incluster_config()
# kubernetes.config.load_kube_config()

myCmd = """
 voms-proxy-init --pwstdin -key /etc/grid-certs/userkey.pem \
                  -cert /etc/grid-certs/usercert.pem \
                  --voms=atlas \
                  <  /servicex/secrets.txt
                  """
os.system(myCmd)
f = "/etc/grid-security/x509up"

# Delete existing secret if present
try:
    client.CoreV1Api().delete_namespaced_secret(namespace='default', name=secret_name)
except kubernetes.client.rest.ApiException as api_exception:
    print("Ok ", api_exception)

while True:

    with open(f, 'rb') as proxy_file:
        secret_created = False
        data = {'x509up': base64.b64encode(proxy_file.read()).decode("ascii")}
        secret = client.V1Secret(data=data,
                                 kind='Secret',
                                 type='Opaque',
                                 metadata=client.V1ObjectMeta(
                                     name=secret_name))

        if secret_created:
            client.CoreV1Api().patch_namespaced_secret(name=secret_name,
                                                       namespace='default', body=secret)
        else:
            client.CoreV1Api().create_namespaced_secret(namespace='default', body=secret)
            secret_created = True

    time.sleep(6*60*60)



