from kubernetes import client, config
import base64

config.load_kube_config()
v1 = client.CoreV1Api()
secret = v1.read_namespaced_secret("users", "servicex") # get the secret

data = secret.data # extract .data from the secret
print(data)
# name = secret.metadata.name
# password = secret.data['password'] # extract .data.password from the secret
#
# decoded = base64.b64decode(password) # decode (base64) value from pasw
#
# print ("Secret: " + name)
# print("-------------")
# print("Here you have the data: ")
# print(data) 
# print("COUNTED DATA: " + str(len(data))) # <- ANSWER FOR THE DATA COUNTER
# print("-------------")
# print("Here you have the decoded password: ")
# print(decoded)