import os
import tempfile
from pathlib import PosixPath

import pytest
from func_adl_xAOD.atlas.xaod.executor import atlas_xaod_executor
from xaod_code_generator.ast_translator import AstAODTranslator

from servicex_codegen.code_generator import GenerateCodeException


def test_ctor():
    'Make sure default ctor works'
    a = AstAODTranslator("ATLAS xAOD")
    assert isinstance(a.executor, atlas_xaod_executor)


def test_translate_good(mocker):
    with tempfile.TemporaryDirectory() as tmpdirname:
        exe = mocker.MagicMock()

        os.environ['TEMPLATE_PATH'] = "xaod_code_generator/templates/transform_single_file.sh"
        os.environ['CAPABILITIES_PATH'] = "transformer_capabilities.json"
        query = "(call ResultTTree (call Select (call SelectMany (call EventDataset (list 'localds://did_01')))))"  # NOQA E501
        translator = AstAODTranslator(exe=exe)
        generated = translator.generate_code(
            query,
            cache_path=tmpdirname)

        assert generated.output_dir == tmpdirname
        exe.apply_ast_transformations.assert_called()
        assert exe.write_cpp_files.call_args[0][1] == PosixPath(tmpdirname)


def test_translate_no_code(mocker):
    with tempfile.TemporaryDirectory() as tmpdirname:
        exe = mocker.MagicMock()

        translator = AstAODTranslator(exe=exe)
        with pytest.raises(GenerateCodeException):
            translator.generate_code("", cache_path=tmpdirname)
