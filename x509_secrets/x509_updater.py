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
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--secret",
                    help="Name of kubernetes secret to save proxy to",
                    dest='secret', action='store',
                    required=False, default=None)

parser.add_argument("--voms",
                    help="Name of CERN virtual org to authenticate against",
                    dest='voms', action='store',
                    required=True)

args = parser.parse_args()

if args.secret:
    secret_name = args.secret
    print("Configuring "+secret_name)
    kubernetes.config.load_incluster_config()

    # For command line testing
    # kubernetes.config.load_kube_config()

    pod_namespace = os.environ['MY_POD_NAMESPACE']
else:
    secret_name = None
    print("Saving to docker volume")


myCmd = """
 voms-proxy-init --pwstdin -key /etc/grid-certs/userkey.pem \
                  -cert /etc/grid-certs/usercert.pem \
                  --voms=%s \
                  <  /etc/grid-certs-ro/passphrase
                  """
os.system(myCmd % args.voms)
f = "/etc/grid-security/x509up"

if secret_name:
    # Delete existing secret if present
    try:
        client.CoreV1Api().delete_namespaced_secret(namespace=pod_namespace, name=secret_name)
    except kubernetes.client.rest.ApiException as api_exception:
        print("No existing secret to delete")

while True:
    if secret_name:
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
                                                           namespace=pod_namespace, body=secret)
                print("Updated proxy cert in  %s" % secret_name)

            else:
                client.CoreV1Api().create_namespaced_secret(namespace=pod_namespace, body=secret)
                print("Created Secret %s" % secret_name)
                secret_created = True

    time.sleep(6*60*60)



