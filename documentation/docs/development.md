# Development

So you want to get involved! The developers welcome community input. The central development area
with all ServiceX repositories can be found [here](https://github.com/ssl-hep). The core steps are
shown in the diagram below.

![Development](img/develop.png)

## Testing new changes

[Instructions for testing new changes. Broadly (1) setup testing environment via ``conda`` or
``virtualenv``, (2) clone the appropriate repository, (3) run ``python -m pip install -e .[test]``
to set up the necessary packages in the environment, and (4) run the tests via ``pytests``.]

## Deploying ServiceX on a Kubernetes cluster

The entire ServiceX stack can be installed using the helm chart contained
[here](https://github.com/ssl-hep/ServiceX). Below is a set of developer instructions for deploying
a production-ready instance of ServiceX on a Kubernetes cluster.

1. Deployment requires access to a Kubernetes cluster. You’ll need to install and set up
``kubectl`` (see
[Install and Set Up kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)) and Helm 3
(see [Installing Helm](https://helm.sh/docs/intro/install/)).

2. Next configure ``kubectl`` to access the appropriate namespace on the cluster with the
kubeconfig file located at ``~/.kube/config``.

3. For complete control over the deployment values in the ServiceX Helm chart, it’s recommended to
check out the ``develop`` branch of ServiceX from GitHub:

        git clone https://github.com/ssl-hep/ServiceX.git
        cd ServiceX
        git checkout develop

4. Add and update the ServiceX Helm chart:

        helm repo add ssl-hep https://ssl-hep.github.io/ssl-helm-charts/
        helm repo update
        helm dependency update servicex

5. ServiceX may require some modifications to the default deployment values to run on your cluster.
In particular, you’ll need your CERN grid certificate to communicate with Rucio. You can see the
default values in ``servicex/values.yaml``. These values can be overridden via a separate yaml
file. For example, to run on SSL-RIVER,

        cat <<EOF > river-values.yaml
        app:
          auth: true
          adminUser: admin
          adminPassword: eto2ipiis1
          ingress:
            enabled: true
        didFinder:
          tag: v1.0-rc.1
          pullPolicy: Always
        codeGen:
          # image: sslhep/servicex_code_gen_func_adl_uproot
          image: sslhep/servicex_code_gen_func_adl_xaod
        rabbitmq:
          service:
            type: NodePort
            nodePort: 30672
        minio:
          ingress:
            enabled: true
            hosts:
            - "servicex-minio.uc.ssl-hep.org"
        gridAccount: bgalewsk
        EOF

6. With the appropriate values, it is now possible to deploy ServiceX via the Helm chart:

        helm install -f river-values.yaml --version v1.0.0-rc.1 rc1-xaod ssl-hep/servicex

7. Initial deployment is typically rapid, with RabbitMQ requiring up to a minute to complete its
initialization. After this all the pods of the new deployment should be ready. If you check the
status of the pods via

        kubectl get pods

    You should soon find that your setup looks comparable to this:

        NAME                                             READY   STATUS    RESTARTS   AGE
        servicex-1579021789-code-gen-7cd998d5b6-nwtgv            1/1     Running   0          49m
        servicex-1579021789-did-finder-7c5cbb4575-52wxf          1/1     Running   0          49m
        servicex-1579021789-minio-78b55bfdf8-mbmmf               1/1     Running   0          49m
        servicex-1579021789-preflight-b748b4dfd-qqt89            1/1     Running   4          49m
        servicex-1579021789-rabbitmq-0                           1/1     Running   0          49m
        servicex-1579021789-servicex-app-98779c79c-cvmqx         1/1     Running   3          49m
        servicex-1579021789-x509-secrets-74f4bcc8bb-5kqvb        1/1     Running   0          49m

8. The new ServiceX deployment should now be ready for business. To try a 10TB scale test check
[ServiceX_scaleTest](https://drive.google.com/open?id=1i5dHWMDEJk5dW0PbxGzo_ccKb8ViP9TCFaS_VpzWAUk).
