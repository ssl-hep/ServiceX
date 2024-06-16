import json
import os

with open('/default_users/users.json', 'r') as f:
    users = json.load(f)


for user in users:
    print(f"Creating user record for {user['name']}")
    command = "poetry run flask user create " \
              " '{}' " \
              " '{}' " \
              " '{}' " \
              " '{}' " \
              " '{}' ".format(user["sub"],
                              user["email"],
                              user["name"],
                              user["institution"],
                              user["refresh_token"])
    os.system(command)
