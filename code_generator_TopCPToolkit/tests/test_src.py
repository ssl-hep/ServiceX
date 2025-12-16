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

from servicex.TopCP_code_generator.request_translator import TopCPTranslator
import os
import tempfile
import pytest
from servicex_codegen.code_generator import GenerateCodeException


def test_generate_code():
    os.environ["TEMPLATE_PATH"] = "servicex/templates/transform_single_file.py"
    os.environ["CAPABILITIES_PATH"] = "transformer_capabilities.json"

    with tempfile.TemporaryDirectory() as tmpdirname:
        # proper query
        translator = TopCPTranslator()
        query = (
            '{"reco": "CommonServices:\\n  systematicsHistogram: \'listOfSystematics\'\\n\\n'
            "PileupReweighting: {}\\n\\nEventCleaning:\\n    runEventCleaning: False\\n"
            "    runGRL: False\\n\\nElectrons:\\n  - containerName: 'AnaElectrons'\\n"
            "    crackVeto: True\\n    IFFClassification: {}\\n    WorkingPoint:\\n"
            "      - selectionName: 'loose'\\n        identificationWP: 'TightLH'\\n"
            "        isolationWP: 'NonIso'\\n        noEffSF: True\\n"
            "      - selectionName: 'tight'\\n        identificationWP: 'TightLH'\\n"
            "        isolationWP: 'Tight_VarRad'\\n        noEffSF: True\\n"
            "    PtEtaSelection:\\n        minPt: 25000.0\\n        maxEta: 2.47\\n"
            "        useClusterEta: True\\n\\n"
            "# After configuring each container, many variables will be saved automatically.\\n"
            "Output:\\n  treeName: 'reco'\\n  vars: []\\n  metVars: []\\n  containers:\\n"
            "      # Format should follow: '<suffix>:<output container>'\\n"
            "      el_: 'AnaElectrons'\\n      '': 'EventInfo'\\n  commands:\\n"
            "    # Turn output branches on and off with 'enable' and 'disable'\\n\\n"
            'AddConfigBlocks: []\\n", "parton": null, "particle": null, "max_events": 100, '
            '"no_systematics": true, "no_filter": false}'
        )

        expected_hash = "ba32662a0909d60d2f7c407e63594061"
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

        # reco is string
        query = (
            '{"reco": 1, "parton": "a", "particle": "c", "max_events": 1, '
            '"no_systematics": false, "no_filter": false}'
        )
        with pytest.raises(TypeError):
            translator.generate_code(query, tmpdirname)


def test_generate_code_with_custom_docker_image():
    os.environ["TEMPLATE_PATH"] = "servicex/templates/transform_single_file.py"
    os.environ["CAPABILITIES_PATH"] = "transformer_capabilities.json"
    os.environ["TOPCP_ALLOWED_IMAGES"] = '["sslhep/custom_image:"]'

    with tempfile.TemporaryDirectory() as tmpdirname:
        translator = TopCPTranslator()
        query = (
            '{"reco": "CommonServices:\\n  systematicsHistogram: \'listOfSystematics\'\\n\\n'
            "PileupReweighting: {}\\n\\nEventCleaning:\\n    runEventCleaning: False\\n"
            "    runGRL: False\\n\\nElectrons:\\n  - containerName: 'AnaElectrons'\\n"
            "    crackVeto: True\\n    IFFClassification: {}\\n    WorkingPoint:\\n"
            "      - selectionName: 'loose'\\n        identificationWP: 'TightLH'\\n"
            "        isolationWP: 'NonIso'\\n        noEffSF: True\\n"
            "      - selectionName: 'tight'\\n        identificationWP: 'TightLH'\\n"
            "        isolationWP: 'Tight_VarRad'\\n        noEffSF: True\\n"
            "    PtEtaSelection:\\n        minPt: 25000.0\\n        maxEta: 2.47\\n"
            "        useClusterEta: True\\n\\n"
            "# After configuring each container, many variables will be saved automatically.\\n"
            "Output:\\n  treeName: 'reco'\\n  vars: []\\n  metVars: []\\n  containers:\\n"
            "      # Format should follow: '<suffix>:<output container>'\\n"
            "      el_: 'AnaElectrons'\\n      '': 'EventInfo'\\n  commands:\\n"
            "    # Turn output branches on and off with 'enable' and 'disable'\\n\\n"
            'AddConfigBlocks: []\\n", "parton": null, "particle": null, "max_events": 100, '
            '"no_systematics": true, "no_filter": false, '
            '"image": "sslhep/custom_image:test"}'
        )

        expected_hash = "f30db9cc91520d3fc08cffd95b072634"
        result = translator.generate_code(query, tmpdirname)

        # is the generated code at least syntactically valid Python?
        try:
            exec(
                open(os.path.join(result.output_dir, "generated_transformer.py")).read()
            )
        except SyntaxError:
            pytest.fail("Generated Python is not valid code")

        assert result.hash == expected_hash
        assert result.image == "sslhep/custom_image:test"
        assert result.output_dir == os.path.join(tmpdirname, expected_hash)


def test_generate_code_fails_with_unknown_selection_key():
    os.environ["TEMPLATE_PATH"] = "servicex/templates/transform_single_file.py"
    os.environ["CAPABILITIES_PATH"] = "transformer_capabilities.json"

    with tempfile.TemporaryDirectory() as tmpdirname:
        translator = TopCPTranslator()
        query = (
            '{"reco": "CommonServices:\\n  systematicsHistogram: \'listOfSystematics\'\\n\\n'
            "PileupReweighting: {}\\n\\nEventCleaning:\\n    runEventCleaning: False\\n"
            "    runGRL: False\\n\\nElectrons:\\n  - containerName: 'AnaElectrons'\\n"
            "    crackVeto: True\\n    IFFClassification: {}\\n    WorkingPoint:\\n"
            "      - selectionName: 'loose'\\n        identificationWP: 'TightLH'\\n"
            "        isolationWP: 'NonIso'\\n        noEffSF: True\\n"
            "      - selectionName: 'tight'\\n        identificationWP: 'TightLH'\\n"
            "        isolationWP: 'Tight_VarRad'\\n        noEffSF: True\\n"
            "    PtEtaSelection:\\n        minPt: 25000.0\\n        maxEta: 2.47\\n"
            "        useClusterEta: True\\n\\n"
            "# After configuring each container, many variables will be saved automatically.\\n"
            "Output:\\n  treeName: 'reco'\\n  vars: []\\n  metVars: []\\n  containers:\\n"
            "      # Format should follow: '<suffix>:<output container>'\\n"
            "      el_: 'AnaElectrons'\\n      '': 'EventInfo'\\n  commands:\\n"
            "    # Turn output branches on and off with 'enable' and 'disable'\\n\\n"
            'AddConfigBlocks: []\\n", "parton": null, "particle": null, "max_events": 100, '
            '"no_systematics": true, "no_filter": false, "unknown_key": "unknown_value"}'
        )

        with pytest.raises(KeyError):
            translator.generate_code(query, tmpdirname)


def test_generate_code_fails_with_missing_required_selection_key():
    os.environ["TEMPLATE_PATH"] = "servicex/templates/transform_single_file.py"
    os.environ["CAPABILITIES_PATH"] = "transformer_capabilities.json"

    with tempfile.TemporaryDirectory() as tmpdirname:
        translator = TopCPTranslator()
        query = (
            '{"reco": "CommonServices:\\n  systematicsHistogram: \'listOfSystematics\'\\n\\n'
            "PileupReweighting: {}\\n\\nEventCleaning:\\n    runEventCleaning: False\\n"
            "    runGRL: False\\n\\nElectrons:\\n  - containerName: 'AnaElectrons'\\n"
            "    crackVeto: True\\n    IFFClassification: {}\\n    WorkingPoint:\\n"
            "      - selectionName: 'loose'\\n        identificationWP: 'TightLH'\\n"
            "        isolationWP: 'NonIso'\\n        noEffSF: True\\n"
            "      - selectionName: 'tight'\\n        identificationWP: 'TightLH'\\n"
            "        isolationWP: 'Tight_VarRad'\\n        noEffSF: True\\n"
            "    PtEtaSelection:\\n        minPt: 25000.0\\n        maxEta: 2.47\\n"
            "        useClusterEta: True\\n\\n"
            "# After configuring each container, many variables will be saved automatically.\\n"
            "Output:\\n  treeName: 'reco'\\n  vars: []\\n  metVars: []\\n  containers:\\n"
            "      # Format should follow: '<suffix>:<output container>'\\n"
            "      el_: 'AnaElectrons'\\n      '': 'EventInfo'\\n  commands:\\n"
            "    # Turn output branches on and off with 'enable' and 'disable'\\n\\n"
            'AddConfigBlocks: []\\n", "parton": null, "particle": null, "max_events": 100, '
            '"no_systematics": true}'
        )

        with pytest.raises(ValueError):
            translator.generate_code(query, tmpdirname)


def test_app():
    import servicex.TopCP_code_generator

    servicex.TopCP_code_generator.create_app()
