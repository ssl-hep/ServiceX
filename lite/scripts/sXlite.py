
import kubernetes
from kubernetes import client


class sXlite:
    def __init__(self):
        kubernetes.config.load_kube_config()

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
    sXlite()
