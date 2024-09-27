"""
Step 0: Start the codegen container
Step 1: Send the request with the query
Step 3: Set up the x509 proxy at /tmp -- do this manually because you have to provide passphrase
Step 4: Run the docker compose up with the relevant root file

Input: Query, Root file and output format
"""
import requests
import subprocess
import os
from requests_toolbelt.multipart import decoder
from io import BytesIO
from zipfile import ZipFile
import time
import yaml
import argparse


class ConfigReader:
    
    def __init__(self, file):
        self._file = file
        self._config = None

    def read_config_file(self):
        with open(self._file) as yaml_file:
            self._config = yaml.safe_load(yaml_file.read())

    def get_config(self):
        return self._config

def docker_compose_up():
    subprocess.run(["docker", "compose", "up", "-d", "--remove-orphans"])

def docker_compose_down():
    subprocess.run(["docker", "compose", "down"])

def send_request(query, port):
    post_url = f"http://localhost:{port}"
    postObj = {"code": query}
    result = requests.post(post_url + "/servicex/generated-code", json=postObj)
    return result


def generate_zipfile(result, output_folder):
    decoder_parts = decoder.MultipartDecoder.from_response(result)
    zipfile = decoder_parts.parts[3].content
    zipfile = ZipFile(BytesIO(zipfile))

    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    zipfile.extractall(output_folder)


def run_docker_compose_for_science(image, filepath):
    subprocess.run(["docker", "compose", "up", "-d", "--remove-orphans"])


def send_root_file_to_science(root_file, output_file, output_format):
    subprocess.run(["docker", "compose", "run", "science", "python",
                    "/generated/transform_single_file.py",
                    root_file, output_file, output_format])


def run_x509_proxy(proxy_image = "sslhep/x509-secrets:develop"):
    my_env = os.environ.copy()
    subprocess.run(["docker" ,"run", "-it", "--mount", f"type=bind,source={my_env['HOME']}/.globus,readonly,target=/globus",
                    "-v", "/tmp:/tmp", "--rm", proxy_image,
                    "voms-proxy-init", "-voms", "atlas", "-cert",
                    "/globus/usercert.pem", "-key", "/globus/userkey.pem" ,"-out", "/tmp/x509up"
                    ]
                    )


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description='Run the servicex codegen and science container')
        parser.add_argument('--proxy_image', help='Run the x509 proxy for image')
        args = parser.parse_args()
        if args.proxy_image:
            run_x509_proxy(proxy_image = args.proxy_image)
        
        a = ConfigReader("config.yml")
        a.read_config_file()
        docker_compose_up()
        time.sleep(10)

        result = send_request(
                            query=a.get_config()['codegen']['query'] , #query,#,
                            port=a.get_config()['codegen']['port'])
        generate_zipfile(result, output_folder="temp1")


        send_root_file_to_science(
            root_file= a.get_config()['science']['rootfile'],
            output_file=a.get_config()['science']['outputfile'],
            output_format=a.get_config()['science']['outputformat']
        )
    finally:
        docker_compose_down()
