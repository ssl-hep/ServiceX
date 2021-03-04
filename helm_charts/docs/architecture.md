# ServiceX Architecture

## Frontend

 ServiceX is accessed via clients distributed as Python packages. There is one client for each query language that may be used to access ServiceX. While it is possible to install clients individually, the [servicex-clients](https://pypi.org/project/servicex-clients/) umbrella package lists all of them as dependencies, so that they can all be installed with a single command: `pip install servicex-clients`.

 The individual clients are as follows:
 - [func-adl-servicex](https://pypi.org/project/func-adl-servicex/) for the func-ADL query language Supports both xAOD and uproot files.
 - [tcut-to-qastle](https://pypi.org/project/tcut-to-qastle/) translates TCut selection strings. Supports only uproot files.

 Each of the above clients provides an API for specifying a query, which is ultimately represented as an abstract syntax tree in [Qastle](https://github.com/iris-hep/qastle). The `qastle` is then handed off to the frontend package, which manages the interaction with ServiceX.

The [ServiceX frontend](https://pypi.org/project/servicex/) package contains the code for communicating with a ServiceX backend. The workflow is as follows:
 - Given a query, the ServiceX frontend constructs a JSON payload for the request. The JSON payload contains the `qastle`, the DID, and anything else necessary to run the query. 
 - It then hashes the request and checks a local cache which it maintains.
   - If the request is in the local request cache, then the system tries to load the data from the local disk cache. If it can't be found on the local disk cache, it requests the data from the backend. If any of these steps fail, then it moves onto the below step.
   - Otherwise, it submits a new transformation request to the backend.

Some technical details of the above process:

- Since the JSON payload completely specifies a request to run on the backend, hashing it becomes a cache lookup key
- The cache is maintain on a local disk (its location is configurable)
- The frontend can deliver the data several ways:
  - Wait until the complete transform request has occurred, or return the data bit-by-bit as each piece of work is finished by ServiceX
  - The data can be copied locally to a file by the frontend code, or a valid Minio URL can be returned instead (valid for about one day after the request), and, as a last option, as a single large `awkward` or `pandas` object. In the case of `awkward`, lazy arrays are used. In the case of `pandas` the data must be rectilinear, and fit in memory.
  - The data comes back as a ROOT file or `parquet` file, depending if you ask for the `xAOD` backend or the `uproot` backend. This is backed into the transformers that operate on these two types of files, and does need to be fixed. If you ask for an `awkward` or `pandas.DataFrame` the format conversion is handled automatically.
- Errors that occur during the transformation on the backend are reported as python exceptions by the frontend code.

<B>Q:
  * TODO:
    * Fix schema - transformers also talk to RMQ 
    * Fix schema - what talks to postgresql? </B>

## Backend

 The ServiceX backend is distributed as a Helm chart for deployment to a Kubernetes cluster. The [chart](https://github.com/ssl-hep/ServiceX.git) a number of microservices, described in the sections below.

<B>Q: What rights does it require on K8s cluster?</B>

![Architecture](img/sx-architecture.png)

### [ServiceX API Server](https://github.com/ssl-hep/ServiceX_App.git) (Flask app)
This is the main entry point to ServiceX, and can be exposed outside the cluster. It provides a REST API for creating transformation requests, posting and retrieving status updates, and retrieving the results. 
 
It also serves a frontend web application where users can authenticate via Globus and obtain ServiceX API tokens. 
Authentication is optional, and may be enabled on a per-deployment basis (see below for more details).

Potential roadmap features for the web frontend include a dashboard of current / past requests, 
and an administrative dashboard for managing users and monitoring resource consumption.

#### **Authentication and Authorization**

If the `auth` flag is set to True when ServiceX is deployed, 
requests to the API server must include a JWT access token.

To authorize their requests, users must provide a ServiceX API Token (JWT refresh token) 
in their `servicex.yaml` file. The frontend Python client will use this to obtain access tokens.

Users can obtain a ServiceX API token by visiting the frontend web application.
Users must authenticate by signing in to Globus via the identity provider of choice.
New accounts will be marked as pending, and can be approved by the deployment's administrators.
This can be done via Slack if the webhook is configured.
Once approved, new users will receive a welcome email via Mailgun (if configured).

Future versions of ServiceX may support disabling Globus auth and the internal user management system, but retaining the JWT system. 
ServiceX API Tokens would need to be generated externally using the same secret used for the deployment.

#### **Endpoints**
 
 <B> Q:
   * REST API
     * Where is OpenAPI description/documentation?   
   * WEB frontend:
     * "... and retrieving the results" Really? I don't think data goes through it but directly from minio to user. This is a very important point.
 </B>

### X509 Proxy Renewal Service
 This service uses the provided grid certificate and key to authenticate against a VOMS proxy server. This generates an X509 proxy which is stored as a Kubernetes Secret. Proxy is renewed once per hour. 
 
 <B> TODO: 
 * should be changed to once per 10 or 23h</B>

### Database
The ServiceX API server stores information about requests, files, and users (if authentication is enabled) in a relational database. The default database is PostgreSQL, without persistance. Another option is SQLite. 
The API server uses SQLAlchemy as an ORM (with Alembic and Flask-Migrate for schema changes).
No other microservices communicate with the database.

![Schema](img/sx-schema.png)
 <B>We need more details here:
 * is data removed once request has been processed?
 * Why is this done? 
 * How will data be used/presented?
 * Could we know eg. slim and skim factors for each request?</B>

### DID Finder
Service which looks up a datasets that should be processed, gets a list of paths and number of events for all the files in the dataset. 
This is done usig the Rucio API. The DID finder uses an x509 proxy to authenticate to Rucio. 

<B>Q:
  * How does it handle multiple replicas of the same files?
  * Are there retries?
  * Does it sum up data size?</B>

### Code Generator
Code generators are microservices which take [`qastle`](https://github.com/iris-hep/qastle) as input and generate C++ source code which transforms files of a given type (e.g. xAOD).
Each deployment must specify a single code generator. As a result, each ServiceX deployment is specific to a (query language, file type) pair. The code generators run in separate containers because they have python versioning requirements that may be different from other components of ServiceX.

Code generation is supported for the following (query language, file type) pairs:
- [funcADL/xAOD](https://github.com/ssl-hep/ServiceX_Code_Generator_FuncADL_xAOD)
- [funcADL/uproot](https://github.com/ssl-hep/ServiceX_Code_Generator_FuncADL_uproot)

 <B>Q:
 * what happens to the generated code? Stored somewhere? Can it be looked up?
 * Can the code generators be consolidated in any way, so that they depend only on the file type, or nothing at all?
 </B>

### RabbitMQ 
 Coordinates messages between microservices. A queue is created for each transformation request. One message is placed in the queue per file. Transformers consume messages while one is available and transform the corresponding file.
 
 <B>Q:
   * any other queues?
   * any other functionality except DID-finder adding messages and transformers consuming them?
   * Any message lifetime?
   * Are messages peristified in case of restart?</B>

### Minio
 Minio stores file objects associated with a given transformation request. Can be exposed outside the cluster via a bundled ingress.

 <B>Q:
   * any cleanup? manual or automatic? if automatic, what is the cleanup policy?
   * do we have at least a way to find out who/what uses space in Minio? 
   * can we see how much space is left? 
   * persistent between servicex/k8s restart?
   * do we know throughput we are generating on it?
   * do we know how often data gets written and not read out?
   * do we know how many times are data re-read?</B>

### Kafka
 Kafka used to be an option for output.

 <B>TODO:
  * if abandoned, it should be removed everywhere. Currently search for "kafka" returns 257 results in 34 files.
 </B>

### Pre-Flight Check 
 Attempts to transform a sample file using the same Docker image as the transformers. If this fails, no transformers will be launched.
 
 <B>TODO:
   * enable autoscaler. Since autoscaling will be default, it will newer start a lot of transformers right away but only one. This one will effectively serve as a check.
   * Figure out what needs to be done to get this do compilation so it is not performed at each transformer. Rename accordingly.

  Q:
   * is it optional? If not, can it be made optional? 
 </B>

### Code generators
 These are flask web servers that get a query string and return a zip file containing 6 files that can be compiled and run by a transformer. Currently there are two different generators:
 * FuncADL_uproot
 * FuncADL_xAOD

 <B>Q:
 * Can one have two or more of generators in one deployment?
 * Why is this needed in each deployment and not one central service?
 </B>   

### Transformers
 Transformers are the worker pods for a transformation request. They get generated transformer code from Code generator servers, compile it, and then subscribe to the RabbitMQ topic for the request. They will listen for a message (file) from the queue, and then attempt to transform the file. If any errors are encountered, they will post a status update and retry. Once the max retry limit is reached, they will mark the file as failed. If the file is transformed successfully, they will post an update and mark the file as done. A single transformer may transform multiple files. Once all files are complete for the transformation request, they are spun down.

<B>Q:
 * Can one transformer do multiple different requests?
 * How do they get data? Is it always root:// protocol?
 * What will be fairshare policy?
 * What happens if a file transformation fails on all retries? 
 * Is there something stoping them when required number of events has been processed?</B>
</B>



## Error handling

There are several distinct kinds of errors:
* user request is not correct
* data is inaccessible
* servicex internal issue
* timeouts

<B>TODO:
 * describe all the failure modes and how are they handled. 
</B>

## Logging

<B>Q:
 * Only kubectl log ... for the servicex itself?
 * No logs for user? How user finds out that eg. one of the files is being fetched from Canada and will take forewer? Or that the file is corrupted?
</B>

## Monitoring and Accounting
 There is a limited support for Elasticsearch based accounting. It requires direct connection to ES and account. Only sends and updates requests and file paths.
 
<B>TODO:
 * describe current Monitoring and Accounting
 * if elasticsearch will be used, it should be fronted with a central logstash and enabled by default for all servicex instances. Much more data should be reported to it. If not, it should be removed.
</B> 


