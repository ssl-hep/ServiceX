import importlib.util
import sys
import types
from pathlib import Path


class FakeArray:
    fields = ("x", "y")

    def __getitem__(self, field):
        return f"array-{field}"


class FakeWritable:
    def __init__(self):
        self.extended = []

    def extend(self, data):
        self.extended.append(data)


class FakeWriter:
    def __init__(self):
        self.objects = {}
        self.mktree_calls = []
        self.mkrntuple_calls = []

    def __contains__(self, key):
        return key in self.objects

    def __getitem__(self, key):
        return self.objects[key]

    def mktree(self, key, data):
        self.mktree_calls.append((key, data))
        self.objects[key] = FakeWritable()

    def mkrntuple(self, key, data):
        self.mkrntuple_calls.append((key, data))
        self.objects[key] = FakeWritable()


def load_transform_module(monkeypatch):
    generated_transformer = types.SimpleNamespace(run_query=lambda _: None)
    monkeypatch.setitem(sys.modules, "generated_transformer", generated_transformer)

    module_path = (
        Path(__file__).parents[1]
        / "uproot_code_generator"
        / "templates"
        / "transform_single_file.py"
    )
    spec = importlib.util.spec_from_file_location(
        "funcadl_uproot_transform_single_file", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_root_file_writer_creates_and_extends_tree(monkeypatch):
    module = load_transform_module(monkeypatch)
    writer = FakeWriter()
    data = FakeArray()

    module.root_write_table_data("root-file", writer, "events", data)
    module.root_write_table_data("root-file", writer, "events", data)

    expected_tree_data = {"x": "array-x", "y": "array-y"}
    assert writer.mktree_calls == [("events", expected_tree_data)]
    assert writer["events"].extended == [expected_tree_data]


def test_rntuple_writer_creates_and_extends_rntuple(monkeypatch):
    module = load_transform_module(monkeypatch)
    writer = FakeWriter()
    data = FakeArray()

    module.root_write_table_data("root-rntuple", writer, "events", data)
    module.root_write_table_data("root-rntuple", writer, "events", data)

    assert writer.mkrntuple_calls == [("events", data)]
    assert writer["events"].extended == [data]


def test_transform_writes_empty_rntuple(monkeypatch, tmp_path):
    module = load_transform_module(monkeypatch)
    empty_array = module.ak.Array({"x": []})
    fake_writer = FakeWriter()

    class FakeRecreate:
        def __enter__(self):
            return fake_writer

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    module.generated_transformer.run_query = lambda _: empty_array
    monkeypatch.setattr(
        module.uproot, "recreate", lambda *_args, **_kwargs: FakeRecreate()
    )

    total_events, output_size = module.transform_single_file(
        "input.root", tmp_path / "output.root", "root-rntuple"
    )

    assert total_events == 0
    assert output_size == 0
    assert fake_writer.mkrntuple_calls == [(module.default_tree_name, empty_array)]
