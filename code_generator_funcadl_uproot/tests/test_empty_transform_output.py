import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import awkward as ak
import numpy as np
import pyarrow.parquet as pq
import pytest
import uproot


class NoMatchingTreeError(ValueError):
    pass


@pytest.fixture
def transform(monkeypatch):
    generated = ModuleType("generated_transformer")
    generated.NoMatchingTreeError = NoMatchingTreeError
    monkeypatch.setitem(sys.modules, generated.__name__, generated)
    template = (
        Path(__file__).parents[1]
        / "uproot_code_generator"
        / "templates"
        / "transform_single_file.py"
    )
    spec = importlib.util.spec_from_file_location("funcadl_writer", template)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.transform_single_file, generated


@pytest.mark.parametrize("output_format", ["root-file", "root-rntuple", "parquet"])
def test_missing_tree_writes_empty_file(transform, tmp_path, output_format):
    write, generated = transform

    def run_query(_):
        raise NoMatchingTreeError("The requested tree is absent")

    generated.run_query = run_query
    path = tmp_path / "output"
    rows, size = write("input.root", path, output_format)

    assert rows == 0
    assert size == path.stat().st_size > 0
    if output_format == "parquet":
        table = pq.read_table(path)
        assert table.num_rows == table.num_columns == 0
    else:
        with uproot.open({path: None}) as output:
            assert output.keys() == []


@pytest.mark.parametrize("output_format", ["root-file", "root-rntuple", "parquet"])
def test_zero_rows_preserve_projected_field(transform, tmp_path, output_format):
    write, generated = transform
    generated.run_query = lambda _: ak.Array({"value": np.array([], dtype=np.int64)})
    path = tmp_path / "output"
    rows, size = write("input.root", path, output_format)

    assert rows == 0
    assert size == path.stat().st_size > 0
    if output_format == "parquet":
        table = pq.read_table(path)
        assert table.num_rows == 0
        assert table.column_names == ["value"]
    else:
        with uproot.open({path: None}) as output:
            tree = output["servicex"]
            assert tree.num_entries == 0
            assert tree.keys() == ["value"]


def test_other_query_errors_are_still_failures(transform, tmp_path):
    write, generated = transform

    def run_query(_):
        raise ValueError("A projected branch is missing")

    generated.run_query = run_query
    path = tmp_path / "output.parquet"
    with pytest.raises(RuntimeError, match="projected branch is missing"):
        write("input.root", path, "parquet")
    assert not path.exists()
