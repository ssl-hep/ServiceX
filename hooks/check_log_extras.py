#!/usr/bin/env python
"""Pre-commit hook: validate logging extra= keys against logging_schema.json."""
import argparse
import ast
import json
import sys
from pathlib import Path

LOG_METHODS = frozenset(
    {"debug", "info", "warning", "warn", "error", "critical", "exception", "fatal", "log"}
)


def load_schema(schema_path: str) -> frozenset:
    path = Path(schema_path)
    if not path.exists():
        print(f"check-log-extras: schema file not found: {schema_path}", file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(path.read_text())
        return frozenset(data["properties"].keys())
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"check-log-extras: invalid schema file {schema_path}: {exc}", file=sys.stderr)
        sys.exit(1)


def _extract_literal_keys(node):
    """Return a list of (key_str, lineno) for fully-literal extra= dicts, or None to skip."""
    if isinstance(node, ast.Dict):
        # Any spread (**x) means a None key in ast.Dict.keys
        if any(k is None for k in node.keys):
            return None
        keys = []
        for k in node.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                keys.append((k.value, k.lineno))
            else:
                # Computed key (f-string, variable, etc.) — skip the whole dict
                return None
        return keys
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _extract_literal_keys(node.left)
        right = _extract_literal_keys(node.right)
        if left is None or right is None:
            return None
        return left + right
    # Variable, call, ternary, etc. — skip
    return None


class LogExtraVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str, allowed_keys: frozenset, require_extras: bool):
        self.filepath = filepath
        self.allowed_keys = allowed_keys
        self.require_extras = require_extras
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr in LOG_METHODS:
            extra_kw = next((kw for kw in node.keywords if kw.arg == "extra"), None)
            if extra_kw is None:
                if self.require_extras:
                    self.errors.append(
                        f"{self.filepath}:{node.lineno}: log call is missing extra="
                    )
            else:
                keys = _extract_literal_keys(extra_kw.value)
                if keys is None:
                    self.warnings.append(
                        f"{self.filepath}:{extra_kw.value.lineno}: "
                        f"extra= value is not a literal dict — skipping schema validation"
                    )
                else:
                    for key, lineno in keys:
                        if key not in self.allowed_keys:
                            self.errors.append(
                                f"{self.filepath}:{lineno}: invalid logging extra key: '{key}'"
                            )
        self.generic_visit(node)


def check_file(
    filepath: str, allowed_keys: frozenset, require_extras: bool
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for the given file."""
    source = Path(filepath).read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        print(f"check-log-extras: syntax error in {filepath}: {exc}", file=sys.stderr)
        return [], []
    visitor = LogExtraVisitor(filepath, allowed_keys, require_extras)
    visitor.visit(tree)
    return visitor.errors, visitor.warnings


def main():
    parser = argparse.ArgumentParser(description="Validate logging extra= keys against schema.")
    parser.add_argument(
        "--schema",
        default="logging_schema.json",
        help="Path to logging_schema.json (default: logging_schema.json)",
    )
    parser.add_argument(
        "--require-extras",
        action="store_true",
        help="Fail if any log call is missing extra=",
    )
    parser.add_argument("files", nargs="*", help="Python files to check")
    args = parser.parse_args()

    allowed_keys = load_schema(args.schema)
    all_errors: list[str] = []
    all_warnings: list[str] = []
    for filepath in args.files:
        errors, warnings = check_file(filepath, allowed_keys, args.require_extras)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    for warning in all_warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    for err in all_errors:
        print(err)

    sys.exit(1 if all_errors else 0)


if __name__ == "__main__":
    main()
