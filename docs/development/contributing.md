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
    - If you are a not a member of the `ssl-hep` GitHub organization,
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

We coordinate our efforts on the [IRIS-HEP Slack](http://iris-hep.slack.com).
Come join this intellectual hub!

## Running the Full ServiceX Chart Locally

You can run ServiceX on your laptop using `docker` or another similar tool that supports kubernetes.

### Prerequisites

1. `docker` is installed and `kubernetes` is running (see configuration options).
1. Make sure `kubectl` and `helm` are both installed in the shell you'll be doing your development work.
1. Follow instructions in the deployment guide to install your x509 certificate if you are going to be using any `rucio` or GRID services for your testing.

### Running the chart

1. In the `Servicex/helm` directory run `helm dependency update servicex/`
1. And install the chart with `helm install -f values.yaml servicex-testing .\servicex\`
1. As in the deployment guide, you can now port-forward your servicex `app` and `minio`.

How you write your `values.yaml` will depend a lot on what you are testing. Here is an example of a minimal one that will load up the `develop` tag for all the container images, and expects an ATLAS GRID cert:

```yaml
postgres:
  enabled: true
objectStore:
  publicURL: localhost:9000

gridAccount: <your-user>

x509Secrets:
  # For ATLAS
  vomsOrg: atlas

app:
  ingress:
    host: localhost:5000

transformer:
  cachePrefix: '""'
```

### Making Changes

The best way to work on ServiceX is using the unit tests. That isn't always possible, of course. When it isn't your development cycle will require you to build any changed containers. A possible workflow is:

1. Redeploy the `helm` chart (or perhaps use `upgrade` rather than `install` in the `helm` command) and add `pullPolicy: Never` to the appropriate app section. For example, add it under `app:` in the example file above if you are working on `servicex_app`.
1. Change your code (say, in `servicex_app`).
1. In the directory for the app should be a `Dockerfile`. Do the build, and pay attention to the tag. For example, `docker build -t sslhep/servicex_app:develop .`.
1. Finally restart the pod, which should cause it to pick up the new build. This might kill a port-forward you have in place, so don't forget to restart that!

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
