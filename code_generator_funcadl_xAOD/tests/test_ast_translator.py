from pathlib import Path

import pytest
from func_adl_xAOD.backend.xAODlib.atlas_xaod_executor import \
    atlas_xaod_executor
from servicex.code_generator_service import AstTranslator
from servicex.code_generator_service.ast_translator import \
    GenerateCodeException


def test_ctor():
    'Make sure default ctor works'
    a = AstTranslator()
    assert isinstance(a.executor, atlas_xaod_executor)


def test_translate_good(mocker):
    exe = mocker.MagicMock()

    def write_files(a, p: str):
        with (Path(p) / 'junk.txt').open('w') as b_out:
            b_out.write("hi")

    exe.write_cpp_files.side_effect = write_files

    a = AstTranslator(xaod_executor=exe)
    a.translate_text_ast_to_zip(
        "(call ResultTTree (call Select (call SelectMany (call EventDataset (list 'localds://did_01')))))")

    exe.apply_ast_transformations.assert_called_once()
    exe.write_cpp_files.assert_called_once()


def test_translate_no_code(mocker):
    exe = mocker.MagicMock()

    a = AstTranslator(xaod_executor=exe)
    with pytest.raises(GenerateCodeException):
        a.translate_text_ast_to_zip("")
