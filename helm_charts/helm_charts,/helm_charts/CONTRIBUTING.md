# ServiceX Contributor Guide

Welcome to the ServiceX contributor guide, and thank you for your interest in contributing to the project!

## Overview

ServiceX uses a microservice architecture, and is designed to be hosted on a Kubernetes cluster. The ServiceX project uses a polyrepo strategy for source code management: the source code for each microservice is located in a dedicated repo. Below is a partial list of these repositories:

- [ServiceX](https://github.com/ssl-hep/ServiceX) - Main repository, contains Helm charts for deployment to Kubernetes
- [ServiceX_frontend](https://github.com/ssl-hep/ServiceX_frontend) - The ServiceX Python library, which enables users to send requests to ServiceX. Currently, this is the only ServiceX frontend client.
- [ServiceX_App](https://github.com/ssl-hep/ServiceX_App) - The ServiceX API Server, written in Flask.

Additional repositories related to the project can be found in the [ssl-hep GitHub organization](https://github.com/ssl-hep).

## Development

Feel free to fork any of the above repositories, make a change, and submit a pull request.

### Branching Strategy

ServiceX uses a slightly modified GitLab flow. Each repository has a main branch, usually named `develop` (or `master` for the Python frontend). All changes should be made on feature branches and submitted as PRs to the main branch. Releases are frozen on dedicated release branches, e.g. `v1.0.0-RC.2`. 

## Issues
Please submit issues for bugs and feature requests to the main ServiceX repository (this one).

We manage project priorities with a [zenhub board](https://app.zenhub.com/workspaces/servicex-5caba4288d0ceb76ea94ae1f/board?repos=180217333,180236972,185614791,182823774,202592339).

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
