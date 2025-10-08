import json
import os

options = {
    "reco": {
        "properType": str,
        "properTypeString": "string",
        "fileName": "reco.yaml",
    },
    "parton": {
        "properType": str,
        "properTypeString": "string",
        "fileName": "parton.yaml",
    },
    "particle": {
        "properType": str,
        "properTypeString": "string",
        "fileName": "particle.yaml",
    },
    "max_events": {
        "properType": int,
        "properTypeString": "integer",
        "default": ["-e", "-1"],
        "option": "-e",
        "minimum": -1,
    },
    "no_systematics": {
        "properType": bool,
        "properTypeString": "boolean",
        "ifTrue": ["--no-systematics"],
        "ifFalse": None,
    },
    "no_filter": {
        "properType": bool,
        "properTypeString": "boolean",
        "ifTrue": ["--no-filter"],
        "ifFalse": None,
    },
    "docker_image": {
        "properType": str,
        "properTypeString": "string",
        "default": "sslhep/servicex_science_image_topcp:2.17.0-25.2.45",
        "optional": True,
    },
}


def generate_files_from_query(query, query_file_path):
    jquery = json.loads(query)

    # transformer_image = jquery.get("docker_image", "sslhep/servicex_science_image_topcp:2.17.0-25.2.45")
    # metadata = {
    #     "transformer_image": transformer_image
    # }
    # with open(
    #     os.path.join(query_file_path, "image_metadata.json"), "w"
    # ) as metadata_file:
    #     json.dump(metadata, metadata_file)

    runTopCommand = [
        "runTop_el.py",
        "-i",
        "input.txt",
        "-o",
        "output",
        "-t",
        "customConfig",
    ]

    # ensure all required keys are specified
    for key in options:
        if key not in jquery:
            # Skip optional parameters
            if options[key].get("optional", False):
                continue
            raise ValueError(
                key + " must be specified. May be type None or ",
                options[key]["properTypeString"],
            )

    for key in jquery:
        if key == "docker_image":
            continue

        # ensure only available options are allowed
        if key not in options:
            raise KeyError(
                key + " is not implemented. Available keys: " + str(options.keys())
            )

        # ensure None entries are ignored
        if jquery[key] is None:
            continue

        # type check key
        if not isinstance(jquery[key], options[key]["properType"]):
            raise TypeError(
                key + " must be of type " + options[key]["properTypeString"]
            )

        # check for reco.yaml, parton.yaml and particle.yaml files
        if isinstance(jquery[key], str) and "fileName" in options[key]:
            with open(
                os.path.join(query_file_path, options[key]["fileName"]), "w"
            ) as file:
                file.write(jquery[key])

        # check for toggle option
        elif isinstance(jquery[key], bool):
            if jquery[key]:
                optStr = "ifTrue"
            else:
                optStr = "ifFalse"

            if options[key][optStr] is not None:
                runTopCommand.extend(options[key][optStr])

        # check max events and skip events
        elif isinstance(jquery[key], int):
            if jquery[key] < options[key]["minimum"]:
                raise ValueError(
                    key + " cannot be less than " + str(options[key]["minimum"])
                )
            else:
                runTopCommand.extend([options[key]["option"], str(jquery[key])])

    # make generated_transformer.py
    generated_code = f"""
import subprocess
def runTop_el():
    subprocess.run({runTopCommand}, check=True)
"""
    with open(
        os.path.join(query_file_path, "generated_transformer.py"), "w"
    ) as python_file:
        python_file.write(generated_code)
