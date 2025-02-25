import os
import sys
from pathlib import Path
import subprocess
instance = os.environ.get('INSTANCE_NAME', 'Unknown')
from pathlib import Path
import shutil

def transform_single_file(file_path: str, output_path: Path, output_format: str):
    # create input.txt file for event loop and insert file_path as only line
    with open("input.txt", "w") as f:
        f.write(file_path)
    output_file_name = file_path.replace('/', '-')
    output_file_name = output_file_name.replace(':','_')
    # move reco file to appropriate loacation
    shutil.copyfile("/generated/reco.yaml", os.path.join(os.environ.get("CONFIG_LOC"),"reco.yaml"))
    subprocess.run(["ls", os.environ.get("CONFIG_LOC")])
    subprocess.run("pwd")
    subprocess.run(["runTop_el.py", "-i", "input.txt", "-o", "output", "-t", "customConfig", "-e", "1"])
    subprocess.run(["mv", "output.root", output_path])

if __name__ == "__main__":
    transform_single_file(sys.argv[1], Path(sys.argv[2]), sys.argv[3])