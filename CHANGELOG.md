# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
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