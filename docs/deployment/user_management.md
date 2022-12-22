# User Management
ServiceX can optionally require logins and authenticate users. This is enabled
with `app.auth` set to true. 

You will need to set `app.adminEmail` to the email address for the bootstrapped
admin user. All other users can be added by:
* With the flask CLI, using the `flask user create` command
* From a json secret file mounted in the cluster, identified through the `app.defaultUsers` setting
* The user connects to the dashboard and successfully goes through an OAuth flow. These users may optionally wait in a pending state for approval via a Slack workflow.

Here are each of the mechanisms in more detail:

## Using the Flask CLI
This CLI is currently only available inside a running ServiceX App pod. An 
administrator needs to create a shell in the pod. They can create a single
user with this command:
```shell
%  flask user create SUB EMAIL NAME ORGANIZATION [REFRESH_TOKEN]
```

Where *SUB* is the OAuth provider's `sub` field (for GlobusAuth this is the user's
GlobusAuth ID).

EMAIL, and NAME are self explanitory.

ORGANIZATION is the user's home institution (Such as "University of Illinois",
or "CERN").

If this user has been previously created and a valid refresh token is known for
them this can be optionally added as the last argument.

Now when a user logs in with this sub the first time, they will immediately be 
granted access to the system without being marked as pending. If the refresh
token is provided, the user can submit transform requests with that token 
without having to log into the dashboard at all.

## Loading Default Users Using JSON File
For integration tests, we often redeploy and erase the database. This means that
it is not possible to have long-standing integration tests against these 
instances. We can get around this by publishing a JSON file containing initial
default users as a secret in the cluster. The app will read this secret upon
startup and automatically load them into the datbase.

This file must be named `users.json` and the format should be:
```json
[
  {
    "email": "firstname.secondname@domain.com",
    "institution": "University of Illinois at Urbana-Champaign",
    "name": "Larry S. Ervicex",
    "refresh_token": "This-is-not-really-a-token-SJcGAE",
    "sub": "123-456-7890"
  }
]
```
You install this secret in the cluster with 
```shell
% kubectl create secret generic users --from-file=users.json
```

## Users Creating Accounts by Logging into Dashboard
Users can just visit the deployment's dashboard and log in with the OAuth flow.
If they have been created in the database using any of the above methods, their
account will immediatly be approved. If not, the account will be set to pending
and they will need to be approved with the slack integration.
