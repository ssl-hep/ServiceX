import os
import sys
import time
import base64
from kubernetes import config, dynamic
from kubernetes.client import api_client
from kubernetes.dynamic import exceptions

requests = {'active': [], 'new': [], 'unknown': []}

rmq_pass = ''
rmq_user = os.getenv("RMQ_USER", 'user')
rmq_host = os.getenv("RMQ_HOST", '192.170.241.253')
initial_pods = int(os.getenv("INITIAL_PODS", '15'))
max_pods = int(os.getenv("MAX_PODS", '1000'))

hpa_version = os.getenv("HPA_VERSION", 'v2')
hpa_cpu_utilization = int(os.getenv("HPA_CPU_UTILIZATION", '10'))


class cluster:
    def __init__(self, context) -> None:
        print(f'initializing context:{context}')
        self.client = dynamic.DynamicClient(
            api_client.ApiClient(configuration=config.load_kube_config(context=context))
        )
        # self.service_api = self.client.resources.get(api_version="v1", kind="Service")
        self.node_api = self.client.resources.get(api_version="v1", kind="Node")
        self.secret_api = self.client.resources.get(api_version="v1", kind="Secret")
        self.deployment_api = self.client.resources.get(api_version="apps/v1", kind="Deployment")
        self.cm_api = self.client.resources.get(api_version="v1", kind="ConfigMap")

    def getNodes(self):
        for item in self.node_api.get().items:
            node = self.node_api.get(name=item.metadata.name)
            print(f'{node.metadata.name}')

    def clean_metadata(self, obj):
        obj['metadata'].pop('ownerReferences', None)
        obj['metadata'].pop('managedFields', None)
        obj['metadata'].pop('creationTimestamp', None)
        obj['metadata'].pop('namespace', None)
        obj['metadata'].pop('resourceVersion', None)
        obj['metadata'].pop('uid', None)
        obj.pop('status', None)
        return obj


class sXorigin(cluster):
    def __init__(self) -> None:
        context = os.environ.get('ORIGIN_CONTEXT')
        namespace = os.environ.get('ORIGIN_NAMESPACE')
        if not context or not namespace:
            sys.exit(1)
        super().__init__(context)
        self.ns = namespace

    def read_secret(self, name):
        print(f'reading secret: {name}')
        sec = self.secret_api.get(name=name, namespace=self.ns)
        self.clean_metadata(sec)
        return sec

    def read_configmap(self, name):
        print(f'reading configmap: {name}')
        cm = self.cm_api.get(name=name, namespace=self.ns)
        self.clean_metadata(cm)
        return cm

    def update_requests(self):
        # reset all known to unknown
        requests['unknown'] = requests['active']
        requests['active'] = []
        requests['new'] = []

        for dep in self.deployment_api.get(namespace=self.ns).items:
            if dep.metadata.name.startswith('transformer'):
                req_id = dep.metadata.name[12:]
                if req_id in requests['unknown']:
                    requests['active'].append(req_id)
                    requests['unknown'].remove(req_id)
                else:
                    requests['new'].append(req_id)

    def get_deployment(self, req_id):
        o = self.deployment_api.get(namespace=self.ns, name=f'transformer-{req_id}')
        req_id = o.metadata.name[12:]
        c1 = o.spec.template.spec.containers[0]
        c2 = o.spec.template.spec.containers[1]
        v = o.spec.template.spec.volumes
        dep = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": o.metadata.name},
            "spec": {
                "replicas": 0,
                "selector": {"matchLabels": {'app': o.spec.selector.matchLabels.app}},
                "template": {
                    "metadata": {
                        "labels": {"app": o.spec.template.metadata.labels.app},
                        "annotations": {}
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": c1.name,
                                "image": c1.image,
                                "command": o.spec.template.spec.containers[0].command,
                                "env": [
                                    {"name": "HOST_NAME",
                                     "valueFrom": {
                                         "fieldRef": {"fieldPath": "spec.nodeName"}
                                     }
                                     }
                                ],
                                "volumeMounts": [],
                                "resources": {
                                    "requests": {
                                        "memory": "2Gi",
                                        "cpu": "250m"
                                    },
                                    "limits": {
                                        "memory": "4Gi",
                                        "cpu": "1"
                                    }
                                },
                            },
                            {
                                "name": c2.name,
                                "image": c2.image,
                                "command": o.spec.template.spec.containers[1].command,
                                "env": [
                                    {"name": "HOST_NAME",
                                     "valueFrom": {
                                         "fieldRef": {"fieldPath": "spec.nodeName"}
                                     }
                                     }
                                ],
                                "volumeMounts": [],
                                "resources": {
                                    "requests": {
                                        "memory": "2Gi",
                                        "cpu": "250m"
                                    },
                                    "limits": {
                                        "memory": "4Gi",
                                        "cpu": "1"
                                    }
                                },
                                "args": o.spec.template.spec.containers[1].args
                            }
                        ],
                        "volumes": []
                    }
                }
            }
        }
        for e in c1.env:
            if e.name == 'HOST_NAME':
                continue
            ta = {'name': e.name, 'value': e.value}
            if "XCACHE" in os.environ and e.name == 'CACHE_PREFIX':
                ta['value'] = os.getenv('XCACHE')
            dep['spec']['template']['spec']['containers'][0]['env'].append(ta)
        for e in c2.env:
            if e.name == 'HOST_NAME':
                continue
            ta = {'name': e.name, 'value': e.value}
            if "XCACHE" in os.environ and e.name == 'CACHE_PREFIX':
                ta['value'] = os.getenv('XCACHE')
            dep['spec']['template']['spec']['containers'][1]['env'].append(ta)

        for e in c1.volumeMounts:
            ta = {'name': e.name, 'mountPath': e.mountPath}
            dep['spec']['template']['spec']['containers'][0]['volumeMounts'].append(ta)
        for e in c2.volumeMounts:
            ta = {'name': e.name, 'mountPath': e.mountPath}
            dep['spec']['template']['spec']['containers'][1]['volumeMounts'].append(ta)

        for e in v:
            vo = {'name': e.name}
            if e.emptyDir:
                vo['emptyDir'] = {}
            if e.secret:
                s = e.secret
                vo['secret'] = {'secretName': s.secretName, 'defaultMode': s.defaultMode}
            if e.configMap:
                cm = e.configMap
                vo['configMap'] = {'name': cm.name, 'defaultMode': cm.defaultMode}
            dep['spec']['template']['spec']['volumes'].append(vo)

        sidecar_arg = o['spec']['template']['spec']['containers'][0]['args'][0]

        # replace RMQ address in sidecar_args
        to_replace = sidecar_arg[sidecar_arg.index('amqp://')+7: sidecar_arg.index(':5672')]
        sidecar_arg = sidecar_arg.replace(to_replace, f'{rmq_user}:{rmq_pass}@{rmq_host}')
        dep['spec']['template']['spec']['containers'][0]['args'] = [sidecar_arg]

        print('=========================')
        # print(dep)
        return dep

    def patch_master(self):
        print('patch ingress if needed.')
        print('patch configmap so it ADVERTIZES external URL.')


class sXlite(cluster):
    def __init__(self) -> None:
        context = os.environ.get('SXLITE_CONTEXT')
        namespace = os.environ.get('SXLITE_NAMESPACE')
        if not context or not namespace:
            sys.exit(1)
        super().__init__(context)
        self.ns = namespace
        self.hpa_api = self.client.resources.get(
            api_version=f"autoscaling/{hpa_version}", kind="HorizontalPodAutoscaler")

    def create_secret(self, secret):
        print(f'creating secret: {secret.metadata.name}')
        try:
            secret = self.secret_api.create(body=secret, namespace=self.ns)
            print(f'created secret: {secret.metadata.name}')
        except exceptions.ConflictError:
            print(f'conflict creating secret: {secret.metadata.name}')

    def delete_secret(self, name):
        print(f'deleting secret: {name}')
        try:
            self.secret_api.delete(body={}, name=name, namespace=self.ns)
            print(f'deleted secret: {name}')
        except exceptions.NotFoundError as e:
            print('could not delete resource:', e.summary())

    def create_configmap(self, cm):
        print(f'creating configmap: {cm.metadata.name}')
        try:
            cm = self.cm_api.create(body=cm, namespace=self.ns)
            print(f'created configmap: {cm.metadata.name}')
        except exceptions.ConflictError:
            print(f'conflict creating configmap: {cm.metadata.name}')

    def delete_configmap(self, name):
        print(f'deleting configmap: {name}')
        try:
            self.cm_api.delete(body={}, name=name, namespace=self.ns)
            print(f'deleted configmap: {name}')
        except Exception as e:
            print(f'could not delete configmap:{name}', e)

    def create_deployment(self, dep):
        dep['spec']['replicas'] = initial_pods

        ea = os.getenv("EXTRA_ANNOTATIONS", "")
        if ea:
            ea_key = ea.split(":")[0].strip()
            ea_val = ea.split(":")[1].strip()
            dep['spec']['template']['metadata']['annotations'][ea_key] = ea_val

        site = {"name": "site", "value": os.environ.get('SXLITE_CONTEXT')}
        dep['spec']['template']['spec']['containers'][0]['env'].append(site)
        dep['spec']['template']['spec']['containers'][1]['env'].append(site)

        print(f'creating deployment: {dep}')

        try:
            dep = self.deployment_api.create(body=dep, namespace=self.ns)
            print(f'created deployment: {dep.metadata.name}')
        except exceptions.ConflictError as e:
            print('conflict creating deployment:', e.summary())

    def delete_deployment(self, name):
        print(f'deleting deployment: {name}')
        try:
            self.deployment_api.delete(body={}, name=name, namespace=self.ns)
            print(f'deleted deployment: {name}')
        except Exception as e:
            print(f'could not delete deployment:{name}', e)

    def create_hpa(self, name):
        print(f'creating hpa: {name}')
        hpa = {
            "apiVersion": f"autoscaling/{hpa_version}",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": name,
                "namespace": self.ns,
            },
            "spec": {
                "scaleTargetRef": {
                    "kind": "Deployment",
                    "name": f"transformer-{name}",
                    "apiVersion": "apps/v1"
                },
                "minReplicas": initial_pods,
                "maxReplicas": max_pods,
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": hpa_cpu_utilization
                            }
                        }
                    }

                ]
            }
        }
        try:
            self.hpa_api.create(body=hpa, namespace=self.ns)
            print(f'created hpa: {name}')
        except exceptions.ConflictError:
            print(f'conflict creating hpa: {name}')

    def delete_hpa(self, name):
        print(f'deleting HPA: {name}')
        try:
            self.hpa_api.delete(body={}, name=name, namespace=self.ns)
            print(f'deleted hpa: {name}')
        except Exception as e:
            print(f'could not delete hpa:{name}', e)


if __name__ == '__main__':

    def cleanup():
        sxl.delete_secret('grid-certs-secret')
        sxl.delete_secret('servicex-secrets')
        sxl.delete_secret('servicex-x509-proxy')

    def start():
        sec = sxo.read_secret('grid-certs-secret')
        sxl.create_secret(sec)

        sec = sxo.read_secret('servicex-secrets')
        sxl.create_secret(sec)
        global rmq_pass
        rmq_pass = base64.b64decode(sec.data['rabbitmq-password']).decode()

        sec = sxo.read_secret('servicex-x509-proxy')
        sxl.create_secret(sec)

    sxo = sXorigin()
    sxl = sXlite()

    sxo.patch_master()
    cleanup()
    start()

    count = 0
    while True:
        sxo.update_requests()
        for req_id in requests['new']:
            d = sxo.get_deployment(req_id)
            sxl.create_deployment(d)
            cm = sxo.read_configmap(f'{req_id}-generated-source')
            sxl.create_configmap(cm)
            sxl.create_hpa(req_id)
            requests['active'].append(req_id)

        for req_id in requests['unknown']:
            sxl.delete_hpa(req_id)
            sxl.delete_configmap(f'{req_id}-generated-source')
            sxl.delete_deployment(f'transformer-{req_id}')

        for req_id in requests['active']:
            print(f'req_id: {req_id} still active.')

        count += 1
        if not count % 720 and len(requests['active']) == 0:  # replace secrets
            cleanup()
            start()

        time.sleep(5)
