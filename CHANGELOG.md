# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

1.5.1
September 20, 2024

### Added
- Use Rucio's Site closeness algorithm for replica ordering

### Changed
- Migrate all of the codegens into the values.yaml
- Include full transformer logs on failure
- Update the chart's values.yaml to use tags for the release

### Fixed
- Status change from looking to running

### Removed

### 1.5.0
September 19, 2024
### Added
- Builds for ARM64 architecture

### Changed
- Added database retries to the transform_file_complete endpoint
- Use celery for the transformer sidecar
- Add XrootD retries in the raw uproot generated code

### Fixed
- Permissions in the xAOD DID Finder container

### Removed

### 1.4.0
August 1, 2024
### Added
- Uproot transformer can write Root files #519
- Deploy multiple code generators #536
- Support xCache for CERN Opendata #550
- Uproot-raw: copy histograms, import awkward functions for cuts #770
- Update the transform request document to show the title as well as the kabana url #757
- multi-xcache-support #726
- Python transformer can support multiple trees #572
- Sidecar converts file to parquet for transformers that don't natively support it #607
- XRootD DID Finder #790

### Changed
- 682 web dashboard selection string rendering for python transformer #699
- Moved prefix handling from the DID finder to the transformer #553
- Moved science images to their own repo #571
- Reduced sleeps in the sidecar to increase throughput  #582
- Transformer and sidecar communicate through sockets #597
- Correct support for IPv6 #629
- Reorganized the data model #496
- Cache DID lookups #687
- Update parquet serialization to be compatible with awkward2 #691
- Renamed packages in monorepo to avoid conflicts #695, #696, #697, #793
- DID Finder uses Celery #800

### Fixed
- Log reading issue #780
- Don't Allow Transformer Pod to Die While there are still files to upload to object stpore #748
- Update did finder deployment to find the new x509 secret name #746
- Clean up the prepend_xcache comments #729
- adding missing file-id and fixing time reported by the sidecar #714
- Restart the app pod when the configmap changes #551
- Fixed crash where Logstash port was being cast to int even if not set #621
- DID Finder off-by-one error that was omitting the last file in a dataset #815

### Removed


### 1.3.0
January 11, 2023
### Added
- User commands to list and approve users
- Added dataset manager to cache previously found datasets

### Changed
- Updated funcADL code generator for xAOD
- Updated funcADL code generator for uproot
- Updated uproot science image to uproot5
- Updated several libraries to avoid security vulnerabilities

### Fixed
- Bug where db was initialized twice
- Typo in transformer logging
- Dashboard refresh has been restored

### Removed


### 1.2.2
September 4, 2023
### Added
- Better replica filtering in Rucio DID Finder
- Sidecar can convert files from root to parquet for cases where the transformer can't
- Network configuration in docker images to support IPv6 
### Changed
- Transformer Sidecar and science images communicate over a unix socket instead of the shared volume
### Fixed
- Warnings from GitHub actions
- Bugs when the LogStash host and port are not provided
- Explicitly set POETRY_CACHE_DIR to avoid permission errors
- DB init code that was initializing the database twice
### Removed

### 1.2.1
May 26, 2023
### Added
- Python code generator allows for functions that return a dict of awkward arrays. Each entry goes into its own tree in the root file
- xCache support for CERN Opendata files

### Changed
- Flask version to avoid vulnerability
- Requests library version to avoid vulnerability
- Upgraded alembic library
- .servicex file reports each of the code generators
- Reduced sleep time when sidecar polling for updates. Results in speedup for large datasets

### Fixed
- Typos in documention
- .servicex file not be downloaded from dashboard
- Update usage of codecov to avoid deprecated usage

### Removed
- Science docker images moved to their own repo

### 1.2.0
April 12, 2023

### Added
- Support for multiple code generators
- Support for HTTP access for files. The Rucio DID Finder will attempt to find HTTP sources for the files. Transformers will only use these if the XRootD URIs fail.

### Changed
- Move xCache prefix handling from the DID Finders to the transformers. This simplifies the DID Finders
-  Updated werkzeug library to avoid security vulnerabilities
- Web app restarts when helm chart updates the app.config

### Fixed 
- The python code generator didn't get properly ported to the transformer sidecar architecture. This is now fixed

### Removed


### 1.1.4
February 7, 2023

### Added
- Cron job to clean up Minio storage from old transforms
### Changed

### Fixed 

### Removed


### 1.1.3
January 31, 2023

### Added
- Ability to add users via CLI. These users are pre-authorized and can skip the slack workflow
- Ability to load users with pre-populated tokens from a secret. New deployments can immediately accept users

### Changed

### Fixed
- Documentation build process
- Upgraded libraries to avoid security vulnerabilities

### Removed


### 1.1.1
December 8, 2022

### Added
- Code generator now reports its default transformer image to pave the way for multiple code generators per deployment

### Changed
- Major rewrite of transformer. No longer require ServiceX code in the science image. There is now a sidecar container that contains the serviceX code.
- Use official Docker GitHub action to cache layers and speed up buids
- Major database speedup by dropping unused tables and adding indexes

### Fixed
- Crashing CERN Opendata DID Finder

### Removed

### 1.0.34

### Added
- option to use direct to logstash logging.
- Move to python 3.10
- Link on the dashboard to access logs


### Changed
- Names of DID Finder pod contiainers simplified
- DID Finder and X509 containers to use python 3.9

### Fixed
- Uproot example in docs
- Ability to use standard S3 apis

### Removed
- standalone chart for filebeat logging.

## Unreleased 1.0.30

## 1.0.31

### Added

- DID Finder and Rucio performance updates: file and metadata operations now
occur using bulk updates instead of file by file.  memcached has been added to cache information
from rucio
- Postgresql and MinIO chart changes: ServiceX now uses MinIO 11.2 and PostgreSQL 11.6
as provided by Bitnami

## 1.0.30

### Added

- DID Finder now returns an ordered list of replicas. If transformer is unable
to open a replica then it can go down the list to find an accesible file
- DID finder can take URI parameters `files`, `rucio://datset-name?files=10` and it will
  return only 10 files from the dataset. By default all flies are returned
- DID finder can take URI prameter `get`, `rucio://data-set?get=availible` and only files
  in a dataset that are availible will be returned. If `all` is supplied instead, then all
  files must be returned. Anything less throws an error.
- About page on web ui to show the deployed version information
- xAOD code generator now works with metadata allowing one to alter its behavior on-the-fly to support
  all collections and obejcts in the ATLAS xAOD

### Changed

- In helm chart, split the default transformer image into two values. One for image
name and a second one for just the tag. This makes it easier for the deployment
script to update the transformer tag.
-

### Fixed

- Correct missing permissions required to use POSIX volume for transform results
- Rucio DID Finder correctly handles files for which there are no replicas

### Removed

## 20220323-1932-stable - 2022-03-23

### Added

- noIndex, noFollow to avoid robots crawling of the web frontend
- About page listing versions of all the components
- Added support for requests without rucio scope.

### Fixed

- User dashboard table is now updating again
- Added default transformer tag parameter.
- Correct handling of datasets with file(s) without any replicas.

## [20220311-2056-stable] - 2022-03-16

### Added

- Support for Bring-your-own Object Store

### Changed

- X509 User Proxies are mounted in /tmp so containers can be run without root permissions
- Option to report logical files instead of replicas to support CMS style xCache

### Fixed

- Updated to current version of Bootstrap web page framework

### Removed

- Preflight Check step
- Kafka streaming

## [1.0.0-RC.4] - 2021-10-8

### Added

- Support for xCache in DID Finders
- Sorting of results in web page  
- Cleaned up and improved documentation
- Examples for ATLAS, tcut, and CMS
- ServiceX Logo
- User frontend and dashboard
- Min and Max workers for Autoscaling
- Searchable Logging via FileBeats
- Support for multiple DID Finders via schemes
- CERN OpenData DID Finder
- Mounting secrets instead of reading them from values.yaml
- Option to skip x509
- Option for transformers to write to mounted volumes instead of Minio buckets
- Lat/Long settings for Rucio DID Finder

### Changed

- Make ingress class annotation value configurable
- Default `PullyPolicy` is `Always` for all images
- DIDFinder is now RucioDIDFinder
- Rucio DID Finder uses more efficient MetaLink property to find replicas

### Fixed

- Bug in X509 secrets where it would error out when secret exists
- Inaccuracies in the NOTES for the helm chart
- Autoscaling settings

### Removed

- Direct ElasticSearch logging
- Site option for DID Finder

## [1.0.0-RC.3] - 2020-10-8

### Added

- Globus Auth for new authentication system
- Web frontend for signups, user profiles, and obtaining ServiceX API tokens
- Mailgun support to email new users when their account has been approved
- Migrated documentation to ReadtheDocs
- Complete deployment instructions
- TLS support for ingress
- Tagging transform requests with the submitting user if authentication is enabled
- Default transformer image for deployment
- New deployment information endpoint to find out the ServiceX version, default transformer image, and the current code gen image tag
-

### Changed

- API access tokens obtained using a ServiceX API token (replaces email/password)
- Organized tempalates into folders to make the helm chart more manageable
- Send the Minio url scheme to the client to make it possible to use TLS secured minio ingress
- App version and code gen image tag are recorded in the DB for each transform
- Split the xAOD and Uproot transformer repos
- Add awkward1 library for parquet transform

### Fixed

- Send 404 error when requesting information about a non-existent transform
- Change the WORKDIR back to /home/atlas after all code is installed
- Stop truncating error messages sent back to ServiceX service

### Removed

- Obsolete methods on ServiceXResource class

## [1.0.0-RC.2] - 2020-07-30

### Added

- Make Autoscaling threshold and pod CPU limit configurable
- Validate transformer docker image name against DockerHub
- Slack notification of new user requests
- Minio endpoint is provided to users via transform request
- Database migration via alembic
- Report current status of transform request and support of fatal errors
- User delete endpoint
- Capture more detailed information from users in the new account create form
- Error endpoint to show transformer errors encountered during job
- DID Finder reports fatal error if no files are found for DID
- Split the uproot and xAOD transformer repos

### Changed

- Use email address instead of username to identify users of ServiceX
- Made size of file status info field to be the maximum VARCHAR size
- Removed Atlas refereces from the transfomer docker image
- Cleaned up command line interface to ServiceX CLI

### Fixed

- Pin pip dependencies
- Transaction leak after DID finder request

### Removed

## [1.0.0-RC.1] - 2020-06-25

### Added

- More detailed timestamp logging in transformers
- JWT based user securing of public endpoints
- New user workflow with admin approval of pending users
- Autoscaler for transforms. If enabled, jobs start with one transformer and
then scale up to the requested number as CPU load increases

### Changed

- Improved the performance serialization of Awkward tables into Arrow
- Upgraded to func-adl-uproot==0.11

### Fixed

- Passing chunk size to transformers

### Removed

## [0.4] - 2020-03-26

### Added

- App retries connection to RabbitMQ on startup instead of just falling into Crash Loop
- CLI to install X509 grid certs and secrets into namespace
- Detailed file level logging to a new database table
- Specify a Grid site affinity to DID finder to prefer replicas that are in a particular site
- Detailed timing if kafka and Minio writes

### Changed

- Max size of select statement increased to postgres varchar max
- X509 secrets created and destroyed by helm chart so they don't hang around after deployment deleted
- DID finder requests multiple replicas in each Rucio lookup to speed things up
- Multiple replicas of app can be specified in the deployment
- Prevent EventLoop from sending file I/O stats back to Rucio to improve performance

### Fixed

- Numerous transaction leaks
- DID Finder connection to serviceX retries

### Removed

## [0.3] - 2020-02-17

### Added

- Uproot FuncADL Code Gen
- Uproot FuncADL Transformer
- Ability for transformers to stream to kafka

### Changed

- Made DID Finder scope optional
- Made DID finder site attribute optional
- Remove ATLAS dependencies on DID Finder

### Fixed

- Pick up RabbitMQ password for all references
- Kubernetes 1.16 breaking changes

### Removed

- Pyroot transformer
- Old uproot transformer

## [0.2] - 2020-01-15

### Added

- X509 Proxy Service
- C++ CodeGen
- C++ Transformer
- Provide the Kafka broker to the transformer

## [0.1] - 2019-10-09

### Added

- First working release of ServiceX
