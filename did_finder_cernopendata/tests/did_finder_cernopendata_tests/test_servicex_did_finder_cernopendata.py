import os
import tempfile
from contextlib import contextmanager

import pytest

from did_finder_cernopendata.did_finder import find_files


@pytest.fixture
def mock_cernopendata_client():
    """
    A fixture that creates a mock cernopendata-client script in a temporary directory
    and adds that directory to the PATH. The script can be configured to return a
    specific output or exit code.
    Many thanks to Claude 3.5 Sonnet for this code.
    """
    @contextmanager
    def _mock_cernopendata_client(mock_output=None, mock_exit_code=None):
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock cernopendata-client script
            mock_script_path = os.path.join(temp_dir, "cernopendata-client")
            with open(mock_script_path, "w") as f:
                if mock_exit_code is not None:
                    f.write(f"#!/bin/bash\nexit {mock_exit_code}")
                elif mock_output is not None:
                    f.write(f"#!/bin/bash\necho '{mock_output}'")

            os.chmod(mock_script_path, 0o755)  # Make the script executable

            # Prepare a modified PATH
            original_path = os.environ['PATH']
            os.environ['PATH'] = f"{temp_dir}:{original_path}"

            yield  # This is where the test runs

            # Restore the original PATH
            os.environ['PATH'] = original_path

    return _mock_cernopendata_client


def test_working_call(mock_cernopendata_client):
    with mock_cernopendata_client(mock_output='root://root.idiot.it/dude'):
        iter = find_files('1507', {'request-id': '112233'})
        files = [f for f in iter]

        assert len(files) == 1
        assert isinstance(files[0], dict)
        assert files[0]['paths'][0] == 'root://root.idiot.it/dude'


def test_exit_code_no_output(mock_cernopendata_client):
    with mock_cernopendata_client(mock_exit_code=10):
        iter = find_files('1507',
                          {'request-id': '112233'}
                          )
        with pytest.raises(Exception) as e:
            [f for f in iter]

        assert "10" in str(e)


def test_non_root_return(mock_cernopendata_client):
    with mock_cernopendata_client(mock_output='http://root.idiot.it/dude'):
        iter = find_files('1507',
                          {'request-id': '112233'}
                          )
        with pytest.raises(Exception) as e:
            [f for f in iter]

        assert 'strange' in str(e)


def test_invalid_did_alpha():
    with pytest.raises(Exception) as e:
        [f for f in find_files('dude', {'request-id': '112233'})]

    assert 'number' in str(e)
