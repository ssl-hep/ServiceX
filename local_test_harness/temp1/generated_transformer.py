
import yaml
import os
import json
def make_yaml():
    query = {'CommonServices': {'runSystematics': False}, 'PileupReweighting': {}, 'EventCleaning': {'runEventCleaning': True}, 'Electrons': [{'containerName': 'OutElectrons', 'crackVeto': True, 'IFFClassification': {}, 'WorkingPoint': [{'selectionName': 'loose', 'identificationWP': 'TightLH', 'isolationWP': 'NonIso', 'noEffSF': True}, {'selectionName': 'tight', 'identificationWP': 'TightLH', 'isolationWP': 'Tight_VarRad', 'noEffSF': True}], 'PtEtaSelection': {'minPt': 25000.0, 'maxEta': 2.47}}], 'Output': {'treeName': 'reco', 'vars': [], 'metVars': [], 'containers': {'el_': 'OutElectrons', '': 'EventInfo'}}}
    with open(os.path.join(os.environ.get("CONFIG_LOC"), "reco.yaml"), 'w') as reco:
        yaml.dump(query, reco, default_flow_style=False)
    