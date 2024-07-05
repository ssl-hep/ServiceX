import pytest
from src.servicex_did_finder_xrootd.did_finder import find_files


def test_working_call():
    iter = find_files(('root://eospublic.cern.ch//eos/opendata/atlas/'
                       'OutreachDatasets/2020-01-22/4lep/MC/*'),
                      {'dataset-id': '112233'}
                      )
    files = [f for f in iter]

    assert len(files) == 106
    assert isinstance(files[0], dict)
    sorted_files = sorted(files, key=lambda x: x['paths'][0])
    assert (sorted_files[0]['paths'][0] ==
            ('root://eospublic.cern.ch//eos/opendata/atlas/'
             'OutreachDatasets/2020-01-22/4lep/MC/mc_301215.ZPrime2000_ee.4lep.root')
            )


def test_exception_no_files():
    iter = find_files(('root://eospublic.cern.ch//eos/opendata/atlas/'
                       'OutreachDatasets/2020-01-22/4lep/MC/dummy*'),
                      {'dataset-id': '112233'},
                      )
    with pytest.raises(RuntimeError):
        [f for f in iter]
