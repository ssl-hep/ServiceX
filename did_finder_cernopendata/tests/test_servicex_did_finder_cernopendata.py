from io import TextIOWrapper
from typing import Iterator, List, Optional
import pytest
from src.servicex_did_finder_cernopendata.did_finder import find_files
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from pathlib import Path


@contextmanager
def command_for_files_back(url: str) -> Iterator[Path]:
    with TemporaryDirectory() as tdir:
        path = Path(tdir) / 'runner.py'
        with path.open('w') as tfp:
            emit_lines(tfp, [url])

        yield path


def emit_lines(tfp: TextIOWrapper, lines: Optional[List[str]]):
    if lines is not None:
        for ln in lines:
            if ln.startswith('**'):
                tfp.write(ln[2:])
            else:
                tfp.write(f'print("{ln}")')
            tfp.write('\n')


@contextmanager
def command_exit(exit_code: int, lines: Optional[List[str]] = None) -> Iterator[Path]:
    with TemporaryDirectory() as tdir:
        path = Path(tdir) / 'runner.py'
        with path.open('w') as tfp:
            emit_lines(tfp, lines)
            tfp.write(f'exit ("{exit_code}")')
            tfp.write('\n')

        yield path


@pytest.mark.asyncio
async def test_working_call():
    with command_for_files_back('root://root.idiot.it/dude') as script_name:
        iter = find_files('1507',
                          {'request-id': '112233'},
                          command=f'python {script_name}'
                          )
        files = [f async for f in iter]

        assert len(files) == 1
        assert isinstance(files[0], dict)
        assert files[0]['paths'][0] == 'root://root.idiot.it/dude'


@pytest.mark.asyncio
async def test_exit_code_no_output():
    with command_exit(10) as script_name:
        iter = find_files('1507',
                          {'request-id': '112233'},
                          command=f'python {script_name}'
                          )
        with pytest.raises(Exception) as e:
            [f async for f in iter]

        assert "10" in str(e)


@pytest.mark.asyncio
async def test_exit_with_crash():
    lines = [
        'root://www.root.com/myfiles',
        '**raise Exception("bad juju")'
    ]

    with command_exit(10, lines=lines) as script_name:
        iter = find_files('1507',
                          {'request-id': '112233'},
                          command=f'python {script_name}'
                          )
        with pytest.raises(Exception) as e:
            [f async for f in iter]

        assert "non-xrootd" not in str(e)


@pytest.mark.asyncio
async def test_non_root_return():
    with command_for_files_back('http://root.idiot.it/dude') as script_name:
        iter = find_files('1507',
                          {'request-id': '112233'},
                          command=f'python {script_name}'
                          )
        with pytest.raises(Exception) as e:
            [f async for f in iter]

        assert 'non-xrootd' in str(e)


@pytest.mark.asyncio
async def test_invalid_did_alpha():
    with pytest.raises(Exception) as e:
        [f async for f in find_files('dude', {'request-id': '112233'})]

    assert 'number' in str(e)
