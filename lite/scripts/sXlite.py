import os
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


class cluster:
    def __init__(self, context) -> None:
        client = dynamic.DynamicClient(
            api_client.ApiClient(configuration=config.load_kube_config(context=context))
        )
        # self.service_api = client.resources.get(api_version="v1", kind="Service")
        self.node_api = client.resources.get(api_version="v1", kind="Node")
        self.secret_api = client.resources.get(api_version="v1", kind="Secret")
        self.deployment_api = client.resources.get(api_version="apps/v1", kind="Deployment")
        self.cm_api = client.resources.get(api_version="v1", kind="ConfigMap")

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
    def __init__(self, context='af-admin@af', namespace='servicex') -> None:
        super().__init__(context)
        self.ns = namespace

    def read_secret(self, name):
        sec = self.secret_api.get(name=name, namespace=self.ns)
        self.clean_metadata(sec)
        return sec

    def read_configmap(self, name):
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
                "replicas": initial_pods,
                "selector": {"matchLabels": {'app': o.spec.selector.matchLabels.app}},
                "template": {
                    "metadata": {"labels": {"app": o.spec.template.metadata.labels.app}},
                    "spec": {
                        "containers": [
                            {
                                "name": c1.name,
                                "image": c1.image,
                                "command": ["bash", "-c"],
                                "env": [],
                                "volumeMounts": [],
                                "resources": {"limits": {"cpu": "1"}},
                                "args": []
                            },
                            {
                                "name": c2.name,
                                "image": c2.image,
                                "command": ["bash", "-c"],
                                "env": [],
                                "volumeMounts": [],
                                "resources": {"limits": {"cpu": "1"}},
                                "args": ['-c'],
                            }
                        ],
                        "volumes": []
                    }
                }
            }
        }
        for e in c1.env:
            ta = {'name': e.name, 'value': e.value}
            dep['spec']['template']['spec']['containers'][0]['env'].append(ta)
        for e in c2.env:
            ta = {'name': e.name, 'value': e.value}
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

        sidecar_args = [
            f'PYTHONPATH=/servicex/transformer_sidecar:$PYTHONPATH python /servicex/transformer_sidecar/transformer.py --request-id {req_id} --rabbit-uri amqp://{rmq_user}:{rmq_pass}@{rmq_host}:5672/%2F?heartbeat=9000 --result-destination object-store --result-format root-file'
        ]
        transformer_args = [
            f'until [ -f /servicex/output/scripts/proxy-exporter.sh ];do sleep 5;done && /servicex/output/scripts/proxy-exporter.sh & sleep 5 && cp /generated/transformer_capabilities.json /servicex/output && PYTHONPATH=/generated:$PYTHONPATH bash /servicex/output/scripts/watch.sh python /generated/transform_single_file.py /servicex/output/{req_id}'
        ]
        dep['spec']['template']['spec']['containers'][0]['args'] = sidecar_args
        dep['spec']['template']['spec']['containers'][1]['args'] = transformer_args

        print('=========================')
        # print(dep)
        return dep

    def patch_master(self):
        print('patch ingress if needed.')
        print('patch configmap so it ADVERTIZES external URL.')


class sXlite(cluster):
    def __init__(self, context='admin@river', namespace='servicex-lite') -> None:
        super().__init__(context)
        self.ns = namespace

    def create_secret(self, secret):
        try:
            secret = self.secret_api.create(body=secret, namespace=self.ns)
            print(f'created secret: {secret.metadata.name}')
        except exceptions.ConflictError:
            print(f'conflict creating secret: {secret.metadata.name}')

    def delete_secret(self, name):
        try:
            self.secret_api.delete(body={}, name=name, namespace=self.ns)
            print(f'deleted secret: {name}')
        except exceptions.NotFoundError as e:
            print('could not delete resource:', e.summary())

    def create_configmap(self, cm):
        try:
            cm = self.cm_api.create(body=cm, namespace=self.ns)
            print(f'created configmap: {cm.metadata.name}')
        except exceptions.ConflictError:
            print(f'conflict creating configmap: {cm.metadata.name}')

    def delete_configmap(self, name):
        try:
            self.cm_api.delete(body={}, name=name, namespace=self.ns)
            print(f'deleted configmap: {name}')
        except Exception as e:
            print(f'could not delete configmap:{name}', e)

    def create_deployment(self, dep):
        try:
            dep = self.deployment_api.create(body=dep, namespace=self.ns)
            print(f'created deployment: {dep.metadata.name}')
        except exceptions.ConflictError as e:
            print('conflict creating deployment:', e.summary())

    def delete_deployment(self, name):
        try:
            self.deployment_api.delete(body={}, name=name, namespace=self.ns)
            print(f'deleted deployment: {name}')
        except Exception as e:
            print(f'could not delete deployment:{name}', e)


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
        rmq_pass = base64.b64decode(sec.data['rabbitmq-password'])

        sec = sxo.read_secret('servicex-x509-proxy')
        sxl.create_secret(sec)

    sxo = sXorigin()
    sxl = sXlite()

    sxo.patch_master()
    # cleanup()
    start()

    count = 0
    while True:
        sxo.update_requests()
        for req_id in requests['new']:
            d = sxo.get_deployment(req_id)
            sxl.create_deployment(d)
            cm = sxo.read_configmap(f'{req_id}-generated-source')
            sxl.create_configmap(cm)
            requests['active'].append(req_id)

        for req_id in requests['unknown']:
            sxl.delete_configmap(f'{req_id}-generated-source')
            sxl.delete_deployment(f'transformer-{req_id}')

        for req_id in requests['active']:
            print(f'req_id: {req_id} still active.')

        count += 1
        if not count % 720 and len(requests['active']) == 0:  # replace secrets
            cleanup()
            start()

        time.sleep(5)
