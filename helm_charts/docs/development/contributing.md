# ServiceX Contributor Guide

Welcome to the ServiceX contributor guide, and thank you for your interest in contributing to the project!

## Overview

ServiceX uses a microservice architecture, 
and is designed to be hosted on a Kubernetes cluster. 
The ServiceX project uses a polyrepo strategy for source code management: 
the source code for each microservice is located in a dedicated repo. 

Below is a partial list of these repositories:

- [ServiceX](https://github.com/ssl-hep/ServiceX) - Main repository, contains Helm charts for deployment to Kubernetes
- [ServiceX_frontend](https://github.com/ssl-hep/ServiceX_frontend) - The ServiceX Python library, which enables users to send requests to ServiceX. Currently, this is the only ServiceX frontend client.
- [ServiceX_App](https://github.com/ssl-hep/ServiceX_App) - The ServiceX API Server, written in Flask.

Additional repositories related to the project can be found in the [ssl-hep GitHub organization](https://github.com/ssl-hep).

Please read our [architecture document](https://servicex.readthedocs.io/en/latest/development/architecture/) for more details.

## Branching Strategy

ServiceX uses a slightly modified GitLab flow. Each repository has a main branch, usually named `develop` (or `master` for the Python frontend). All changes should be made on feature branches and submitted as PRs to the main branch. Releases are frozen on dedicated release branches, e.g. `v1.0.0-RC.2`. 

## Development Workflow

1. Set up a local development environment:
    - Decide which microservice (or Helm chart) you'd like to change, 
    and locate the corresponding repository. 
    - If you are a not a member of the IRIS-HEP SSL, 
    fork the repository.
    - Clone the (forked) repository to your local machine:
    ```
    git clone git@github.com:<GitHub username>/ServiceX_App.git
    ```
    - If you created a fork, add the upstream repository as remote:
    ```
    git remote add upstream git@github.com:ssl-hep/ServiceX_App.git
    ```
    - Set up a new environment via ``conda`` or ``virtualenv``.
    - Install dependencies, including test dependencies:
    ```
    python3 -m pip install -e .[test]
    ```
    - If the root directory contains a file named `.pre-commit-config.yaml`,
    you can install the [pre-commit](https://pre-commit.com/) hooks with:
    ```
    pip install pre-commit
    pre-commit install
    ```
1. Develop your contribution:
    - Pull latest changes from upstream:
    ```
    git checkout develop
    git pull upstream develop
    ```
    - Create a branch for the feature you want to work on:
    ```
    git checkout -b fix-issue-99
    ```
    - Commit locally as you progress with `git add` and `git commit`.
1. Test your changes:
    - Run the full test suite with `python -m pytest`, or target specific test files with `python -m pytest tests/path/to/file.py`.
    - Please write new unit tests to cover any changes you make.
    - You can also manually test microservice changes against a full ServiceX deployment by building the Docker image, pushing it to DockerHub, and setting the `image` and `tag` values as follows:
    ```yaml
    app:
      image: <organization>/<image repository>
      tag: my-feature-branch
    ``` 
    - For more details, please read our full 
    [deployment guide](https://servicex.readthedocs.io/en/latest/deployment/basic). 
1. Submit a pull request to the upstream repository.

## Issues
Please submit issues for bugs and feature requests to the [main ServiceX repository](https://github.com/ssl-hep/ServiceX),
unless the issue is specific to a single microservice.

We manage project priorities with a [ZenHub board](https://app.zenhub.com/workspaces/servicex-5caba4288d0ceb76ea94ae1f/board?repos=180217333,180236972,185614791,182823774,202592339).

## Join us on Slack
We coordinate our efforts on the [IRIS-HEP slack](http://iris-hep.slack.com).
Come join this intellectual hub.

## Debugging Tips
Microservice architectures can be difficult to test and debug. Here are some 
helpful hints to make this easier.

1. Instead of relying on the DID Finder to locate some particular datafile, you
can mount one of your local directories into the transformer pod and then 
instruct the DID Finder to always offer up the path to that file regardless of
the submitted DID. You can use the `hostMount` value to have a local directory
mounted into each transformer pod under `/data`. You can use the 
`didFinder.staticFile` value to instruct DID Finder to offer up a file from that
directory.
2. You can use port-forwarding to expose port 15672 from the RabbitMQ pod to 
your laptop and log into the Rabbit admin console using the username: `user` and
password `leftfoot1`. From here you can monitor the queues, purge old messages
and inject your own messages

## Notes for Maintainers

### Hotfixes

If a critical bugfix or hotfix must be applied to a previous release, it should be merged to the main branch and then applied to each affected release branch using `git cherry-pick <merge commit hash> -m 1`. Merge commits have 2 parents, so the `-m 1` flag is used to specify that the first parent (i.e. previous commit on the main branch) should be used 
