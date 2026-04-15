"""Tests for check_log_extras.py.

Each test writes a small Python snippet to a temp file and calls check_file()
directly, making it easy to see exactly what the hook accepts or rejects.
"""

import textwrap

import pytest

from check_log_extras import check_file

# A small fixed set of allowed keys — tests don't depend on the real schema file.
ALLOWED = frozenset({"request_id", "file_id", "dataset_id"})


def make_py(tmp_path, code: str) -> str:
    """Write dedented Python code to a temp file and return the path string."""
    p = tmp_path / "sample.py"
    p.write_text(textwrap.dedent(code))
    return str(p)


# ── accept cases ──────────────────────────────────────────────────────────────


def test_valid_key_accepted(tmp_path):
    path = make_py(
        tmp_path,
        """
        logger.info("msg", extra={"request_id": "abc"})
        """,
    )
    errors, warnings = check_file(path, ALLOWED, require_extras=False)
    assert errors == []
    assert warnings == []


def test_multiple_valid_keys_accepted(tmp_path):
    path = make_py(
        tmp_path,
        """
        logger.info("msg", extra={"request_id": "abc", "file_id": 1})
        """,
    )
    errors, warnings = check_file(path, ALLOWED, require_extras=False)
    assert errors == []
    assert warnings == []


def test_no_extra_without_require_accepted(tmp_path):
    path = make_py(
        tmp_path,
        """
        logger.info("something happened")
        """,
    )
    errors, warnings = check_file(path, ALLOWED, require_extras=False)
    assert errors == []
    assert warnings == []


def test_pipe_merge_of_valid_dicts_accepted(tmp_path):
    path = make_py(
        tmp_path,
        """
        logger.info("msg", extra={"request_id": "x"} | {"file_id": 1})
        """,
    )
    errors, warnings = check_file(path, ALLOWED, require_extras=False)
    assert errors == []
    assert warnings == []


def test_variable_extra_emits_warning_not_error(tmp_path):
    """A variable dict can't be validated statically — warn instead of failing."""
    path = make_py(
        tmp_path,
        """
        ctx = {"request_id": "x"}
        logger.info("msg", extra=ctx)
        """,
    )
    errors, warnings = check_file(path, ALLOWED, require_extras=False)
    assert errors == []
    assert len(warnings) == 1


def test_spread_dict_emits_warning_not_error(tmp_path):
    """A dict with **spread can't be validated statically — warn instead of failing."""
    path = make_py(
        tmp_path,
        """
        logger.info("msg", extra={**base, "request_id": "x"})
        """,
    )
    errors, warnings = check_file(path, ALLOWED, require_extras=False)
    assert errors == []
    assert len(warnings) == 1


# ── reject cases ──────────────────────────────────────────────────────────────


def test_invalid_key_rejected(tmp_path):
    path = make_py(
        tmp_path,
        """
        logger.info("msg", extra={"bad_key": "oops"})
        """,
    )
    errors, warnings = check_file(path, ALLOWED, require_extras=False)
    assert len(errors) == 1
    assert "bad_key" in errors[0]


def test_missing_extra_rejected_when_required(tmp_path):
    path = make_py(
        tmp_path,
        """
        logger.info("something happened")
        """,
    )
    errors, warnings = check_file(path, ALLOWED, require_extras=True)
    assert len(errors) == 1
    assert "missing extra=" in errors[0]


def test_mixed_keys_only_invalid_ones_flagged(tmp_path):
    path = make_py(
        tmp_path,
        """
        logger.info("msg", extra={"request_id": "ok", "typo_key": "bad"})
        """,
    )
    errors, warnings = check_file(path, ALLOWED, require_extras=False)
    assert len(errors) == 1
    assert "typo_key" in errors[0]


def test_pipe_merge_with_invalid_key_rejected(tmp_path):
    path = make_py(
        tmp_path,
        """
        logger.info("msg", extra={"request_id": "x"} | {"bad_key": 1})
        """,
    )
    errors, warnings = check_file(path, ALLOWED, require_extras=False)
    assert len(errors) == 1
    assert "bad_key" in errors[0]


def test_multiple_violations_all_reported(tmp_path):
    """Every bad call in a file is reported, not just the first."""
    path = make_py(
        tmp_path,
        """
        logger.info("one", extra={"bad_one": 1})
        logger.debug("two", extra={"bad_two": 2})
        """,
    )
    errors, warnings = check_file(path, ALLOWED, require_extras=False)
    assert len(errors) == 2
    assert any("bad_one" in e for e in errors)
    assert any("bad_two" in e for e in errors)
