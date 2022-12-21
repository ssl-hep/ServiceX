from kubernetes import client, config
import base64
import json
import os
config.load_kube_config()
v1 = client.CoreV1Api()
secret = v1.read_namespaced_secret("users", "default")
users_encoded = secret.data['users.json']
users_decoded = base64.b64decode(users_encoded)
users = json.loads(users_decoded)

for user in users:
    command = "poetry run flask --app servicex/app.py create " \
              "--sub {} " \
              "--email {} " \
              "--name {} " \
              "--institution {} " \
              "--refresh_token {}".format(user["sub"],
                                          user["email"],
                                          user["name"],
                                          user["institution"],
                                          user["refresh_token"])
    os.system(command)


