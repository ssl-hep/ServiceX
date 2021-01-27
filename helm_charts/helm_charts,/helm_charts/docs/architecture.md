# ServiceX Architecture

![Architecture](img/sx-architecture.png)

## Backend

The ServiceX backend is distributed as a Helm chart for deployment to a Kubernetes cluster. The chart consists of the following components:
- ServiceX API Server (Flask app) - This is the main entry point to ServiceX, and can be exposed outside the cluster via an external ingress. It provides a REST API for creating transformation requests, posting and retrieving status updates, and retrieving the results. It also servers a frontend web application where users can authenticate and obtain ServiceX API tokens.
- PostgreSQL - A relational database which stores information about transformation requests, files, and users.
- DID Finder - Service which looks up a datasets that should be processed, gets a list of paths and number of events for all the files in the dataset. This is done usig Rucio API.
- Code Generator - A microservice which takes a query written in a specific query language (e.g. FuncADL) and generates C++ source code to perform this transformation on files of a given type (e.g. xAOD). As a result, each ServiceX deployment is specific to a (query language, file type) pair.
- X509 Proxy Renewal Service - This service passes the provided grid cert and key to the VOMS proxy server to generate an X509 proxy which is stored as a Kubernetes Secret.
- RabbitMQ - Coordinates messages between microservices. A queue is created for each transformation request. One message is placed in the queue per file. Transformers consume messages while one is available and transform the corresponding file.
- Minio - Minio stores file objects associated with a given transformation request. Can be exposed outside the cluster via a bundled ingress.
- Pre-Flight Check - Attempts to transform a sample file using the same Docker image as the transformers. If this fails, no transformers will be launched.

## Frontend

- 