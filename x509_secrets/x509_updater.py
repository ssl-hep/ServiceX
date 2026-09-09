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
import subprocess
import sys
import time

import kubernetes
from kubernetes import client
import base64
import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "--secret",
    help="Name of kubernetes secret to save proxy to",
    dest="secret",
    action="store",
    required=False,
    default=None,
)

parser.add_argument(
    "--voms",
    help="Name of CERN virtual org to authenticate against",
    dest="voms",
    action="store",
    required=True,
)

parser.add_argument(
    "--loop",
    help="Run forever, updating every six hours",
    dest="loop",
    action="store_true",
)

args = parser.parse_args()

if args.secret:
    secret_name = args.secret
    print("Creating secret:", secret_name)
    kubernetes.config.load_incluster_config()

    # For command line testing
    # kubernetes.config.load_kube_config()

    pod_namespace = os.environ["MY_POD_NAMESPACE"]
else:
    secret_name = None
    print("Saving to docker volume")


myCmd = [
    "voms-proxy-init3",
    "--pwstdin",
    "--key",
    "/etc/grid-certs/userkey.pem",
    "--cert",
    "/etc/grid-certs/usercert.pem",
    "--voms=%s" % args.voms,
]
passphrase_file = "/etc/grid-certs-ro/passphrase"
f = "/tmp/x509up"


def create_proxy():
    try:
        with open(passphrase_file, "rb") as passphrase:
            subprocess.run(myCmd, stdin=passphrase, check=True)
    except (OSError, subprocess.CalledProcessError) as proxy_error:
        print(
            "Failed to create the x509 proxy, leaving any existing proxy untouched:",
            proxy_error,
            file=sys.stderr,
        )
        sys.exit(1)


create_proxy()

if not secret_name:
    sys.exit(0)

while True:
    with open(f, "rb") as proxy_file:
        data = {"x509up": base64.b64encode(proxy_file.read()).decode("ascii")}
    secret = client.V1Secret(
        data=data,
        kind="Secret",
        type="Opaque",
        metadata=client.V1ObjectMeta(name=secret_name),
    )

    try:
        client.CoreV1Api().patch_namespaced_secret(
            name=secret_name, namespace=pod_namespace, body=secret
        )
        print("Updated proxy cert in %s" % secret_name)
    except kubernetes.client.rest.ApiException as api_error:
        if api_error.status != 404:
            raise
        client.CoreV1Api().create_namespaced_secret(
            namespace=pod_namespace, body=secret
        )
        print("Created Secret %s" % secret_name)

    if not args.loop:
        # exit after first pass through
        sys.exit(0)

    time.sleep(6 * 60 * 60)
    create_proxy()
