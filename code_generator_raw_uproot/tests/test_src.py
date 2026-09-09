# Copyright (c) 2019, IRIS-HEP
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from servicex.raw_uproot_code_generator.request_translator import RawUprootTranslator
import importlib.util
import json
import os
import sys
import tempfile
import types
from pathlib import Path

import pytest
from servicex_codegen.code_generator import GenerateCodeException


def test_generate_code():
    os.environ["TEMPLATE_PATH"] = "servicex/templates/transform_single_file.py"
    os.environ["CAPABILITIES_PATH"] = "transformer_capabilities.json"

    with tempfile.TemporaryDirectory() as tmpdirname:
        # proper query
        translator = RawUprootTranslator()
        query = json.dumps(
            [
                {"treename": "sumWeights", "filter_name": ["/totalE.*/"]},
                {
                    "treename": ["nominal", "JET_JER_EffectiveNP_1__1down"],
                    "filter_name": ["/mu_.*/", "runNumber", "lbn"],
                    "cut": "met_met>150e3",
                },
                {"treename": {"nominal": "modified"}, "filter_name": ["lbn"]},
                {"copy_histograms": "CutBookkeeper*"},
            ]
        )
        expected_hash = "a3ac3db03730b67eafccd0fe8ca8f607"

        result = translator.generate_code(query, tmpdirname)

        # is the generated code at least syntactically valid Python?
        try:
            exec(
                open(os.path.join(result.output_dir, "generated_transformer.py")).read()
            )
        except SyntaxError:
            pytest.fail("Generated Python is not valid code")

        assert result.hash == expected_hash
        assert result.output_dir == os.path.join(tmpdirname, expected_hash)

        # empty query
        query = ""
        with pytest.raises(GenerateCodeException):
            translator.generate_code(query, tmpdirname)

        query = json.dumps("abc")
        with pytest.raises(GenerateCodeException):
            translator.generate_code(query, tmpdirname)

        query = json.dumps([{}])
        with pytest.raises(GenerateCodeException):
            translator.generate_code(query, tmpdirname)

        # not JSON at all
        query = "{not json"
        with pytest.raises(GenerateCodeException):
            translator.generate_code(query, tmpdirname)

        # subquery is not a dictionary
        query = json.dumps(["nominal"])
        with pytest.raises(GenerateCodeException):
            translator.generate_code(query, tmpdirname)

        # non-finite floats cannot be written into the generated code
        query = '[{"treename": "nominal", "cut": NaN}]'
        with pytest.raises(GenerateCodeException):
            translator.generate_code(query, tmpdirname)


def test_template_writes_empty_parquet_when_no_tree_is_found(tmp_path, monkeypatch):
    import pyarrow.parquet as pq

    def run_query(file_path):
        # every requested tree is missing, so nothing is yielded
        yield from ()

    generated = types.ModuleType("generated_transformer")
    generated.run_query = run_query
    monkeypatch.setitem(sys.modules, "generated_transformer", generated)

    template_path = (
        Path(__file__).parent.parent / "servicex/templates/transform_single_file.py"
    )
    spec = importlib.util.spec_from_file_location("raw_uproot_template", template_path)
    template = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(template)

    output_path = tmp_path / "output.parquet"
    total_events, output_size = template.transform_single_file(
        "root://example//missing_trees.root", output_path, "parquet"
    )

    assert total_events == 0
    assert output_size == output_path.stat().st_size
    table = pq.read_table(output_path)
    assert table.num_columns == 0
    assert table.num_rows == 0


def test_app():
    import servicex.raw_uproot_code_generator

    servicex.raw_uproot_code_generator.create_app()
