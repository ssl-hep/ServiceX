from test import ConfigReader
import make_query
import json

def main():
    a = ConfigReader("config.yml")
    a.read_config_file()
    cgc = a.get_config()['codegen']
    query = make_query.make_query_string(cgc['query'])
    jquery = json.loads(query)
    with open("queryTest.yaml", "w") as queryTest:
        queryTest.write(jquery["RecoYAML"])
        print(jquery.keys())
        idk = ["1","2","3"]
        print(f"{str(idk)}")
if __name__ == "__main__":
    main()