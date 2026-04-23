# The Admin page

An Admin page is available at `/admin` if `ENABLE_AUTH=True`.

From the admin page, a User Model View is available to interact with individual user records, including toggling whether a user is an admin.

# Reports
There is also a reporting feature. Currently, there is only one report.

## User Transformation Count
Returns a CSV of all users in the database with how many transformations have been run over a period of time (with a default window of 30 days).

# Reports CLI
The reporting module is also available from the flask admin CLI: 

```commandline
$ flask --app 'app:app' reports
Usage: flask reports [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  user-transformation-count

$ flask --app 'app:app' reports user-transformation-count --help
Usage: flask reports user-transformation-count [OPTIONS]

Options:
  --days INTEGER  Number of days to look back
  --help          Show this message and exit.
  
$ flask --app 'app:app' reports user-transformation-count
Name,Email,Institution,Experiment,Transforms (Last 30 Days)
Test User,test@gmail.com,CERN,ATLAS,1
```