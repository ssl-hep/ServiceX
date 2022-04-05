# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased 1.0.30
### Added
- DID Finder now returns an ordered list of replicas. If transformer is unable
to open a replica then it can go down the list to find an accesible file
- About page on web ui to show the deployed version information
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
