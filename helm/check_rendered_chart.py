"""Sanity checks on the output of ``helm template`` for the servicex chart.

Usage: python helm/check_rendered_chart.py RENDERED_YAML [RELEASE_NAME]

- The app.conf in the app ConfigMap must be valid Python, since Flask loads
  it with from_envvar at startup.
- JWT_REFRESH_TOKEN_EXPIRES and JWT_ACCESS_TOKEN_EXPIRES must be an int or
  False, the only forms flask-jwt-extended accepts from a config file.
- VALID_DID_SCHEMES must list exactly the DID finders that have a
  Deployment, and DID_FINDER_DEFAULT_SCHEME must be one of them.
"""

import ast
import re
import sys


def app_conf(documents):
    for doc in documents:
        if re.search(r"^kind: ConfigMap$", doc, re.M):
            m = re.search(r"^  app\.conf: \|\n((?:    .*\n|[ \t]*\n)*)", doc, re.M)
            if m:
                return "\n".join(line[4:] for line in m.group(1).splitlines())
    sys.exit("no ConfigMap with an app.conf key found")


def deployment_names(documents):
    names = []
    for doc in documents:
        if re.search(r"^kind: Deployment$", doc, re.M):
            m = re.search(r"^metadata:\n(?:  .*\n)*?  name: (\S+)$", doc, re.M)
            if m:
                names.append(m.group(1))
    return names


def assignments(source):
    values = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                try:
                    values[target.id] = ast.literal_eval(node.value)
                except ValueError:
                    pass
    return values


def main():
    path = sys.argv[1]
    release = sys.argv[2] if len(sys.argv) > 2 else "test"
    with open(path) as f:
        documents = re.split(r"^---$", f.read(), flags=re.M)

    source = app_conf(documents)
    try:
        compile(source, "app.conf", "exec")
    except SyntaxError as e:
        sys.exit(f"app.conf is not valid Python: line {e.lineno}: {e.msg}")
    config = assignments(source)

    errors = []
    for key in ("JWT_REFRESH_TOKEN_EXPIRES", "JWT_ACCESS_TOKEN_EXPIRES"):
        value = config.get(key)
        if not (value is False or type(value) is int):
            errors.append(f"{key} must be an int or False, got {value!r}")

    prefix = f"{release}-did-finder-"
    finders = {
        name.removeprefix(prefix)
        for name in deployment_names(documents)
        if name.startswith(prefix)
    }
    schemes = config.get("VALID_DID_SCHEMES", [])
    if set(schemes) != finders:
        errors.append(
            f"VALID_DID_SCHEMES {sorted(schemes)} does not match the deployed "
            f"DID finders {sorted(finders)}"
        )
    default = config.get("DID_FINDER_DEFAULT_SCHEME")
    if default not in schemes:
        errors.append(f"DID_FINDER_DEFAULT_SCHEME {default!r} not in {schemes}")

    if errors:
        sys.exit("\n".join(errors))
    print(f"{path}: OK, DID schemes {sorted(schemes)}, default {default!r}")


if __name__ == "__main__":
    main()
