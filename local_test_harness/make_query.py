import json

def make_query_string(queryDict):
    query = dict()
    for key in queryDict:
        if key == "RecoYAML" or key == "PartonYAML" or key == "ParticleYAML":
            with open(queryDict[key], "r") as file:
                query[key] = file.read()
        else:
            query[key] = queryDict[key]
    return json.dumps(query)