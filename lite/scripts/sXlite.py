import kubernetes
from kubernetes import client, watch


class sXorigin:
    def __init__(self) -> None:
        kubernetes.config.load_kube_config()

    def watch(self):
        v1 = client.CoreV1Api()
        count = 10
        w = watch.Watch()
        for event in w.stream(v1.list_namespace, _request_timeout=60):
            print(f"Event: {event['type']} {event['object'].metadata.name}")
            count -= 1
            if not count:
                w.stop()


class sXlite:
    def __init__(self) -> None:
        pass
        # client.CoreV1Api().create_namespaced_secret(
        #     namespace=pod_namespace, body=secret)
        # print("Created Secret %s" % secret_name)
        # secret_created = True

# print("Delete existing secret if present")
# try:
#     client.CoreV1Api().delete_namespaced_secret(
#         namespace=pod_namespace, name=secret_name)
# except kubernetes.client.rest.ApiException as api_exception:
#     print("No existing secret to delete")


if __name__ == '__main__':
    sXorigin()
    sXlite()
    sXorigin.watch()
