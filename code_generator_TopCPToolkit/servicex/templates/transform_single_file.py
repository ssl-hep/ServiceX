import os
import sys
from pathlib import Path
import shutil
import generated_transformer

instance = os.environ.get("INSTANCE_NAME", "Unknown")


def transform_single_file(file_path: str, output_path: Path, output_format: str):
    # create input.txt file for event loop and insert file_path as only line
    with open("input.txt", "w") as f:
        f.write(file_path)

    # move reco.yaml, parton.yaml and particle.yaml if they exist to CONFIG_LOC location
    config_loc = os.environ.get("CONFIG_LOC", os.getcwd())
    if os.path.exists("/generated/reco.yaml"):
        shutil.copyfile(
            "/generated/reco.yaml",
            os.path.join(config_loc, "reco.yaml"),
        )
    if os.path.exists("/generated/parton.yaml"):
        shutil.copyfile(
            "/generated/parton.yaml",
            os.path.join(config_loc, "parton.yaml"),
        )
    if os.path.exists("/generated/particle.yaml"):
        shutil.copyfile(
            "/generated/particle.yaml",
            os.path.join(config_loc, "particle.yaml"),
        )

    generated_transformer.runTop_el()
    shutil.move("output.root", output_path)


if __name__ == "__main__":
    transform_single_file(sys.argv[1], Path(sys.argv[2]), sys.argv[3])
