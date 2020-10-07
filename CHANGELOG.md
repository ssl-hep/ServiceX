# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
## [1.0.0-RC.3] - 2020-10-8
### Added
- Globus Auth for authentication
- Mailgun support to email new users when their account has been approved
- Migrated documentation to readthedocs
- Complete deployment instructions
- TLS support for ingress
- Tagging transform requests with the submitting user
- Default transformer image for deployment
- New deployment information endpoint to find out the serviceX version, default transformer image, and the current code gen image tag
- 
### Changed
- Organized tempalates into folders to make the helm chart more manageable
- Send the Minio url scheme to the client to make it possible to use TLS secured minio ingress
- App version and code gen image tag are recorded in the DB for each transform
- Split the xAOD and Uproot transformer repos
- Add awkward1 library for parquet transform

### Fixed
- Send 404 error when requesting status of a non-existent transform
- Change the WORKDIR back to /home/atlas after all code is installed
- Stop truncating error messages sent back to serviceX service

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