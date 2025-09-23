"""Test custom image tag functionality for TopCP code generator."""

import json
import os
import tempfile
import unittest

from servicex.TopCP_code_generator.query_translate import generate_files_from_query


class TestCustomImageTag(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_custom_image_tag_in_query_validation(self):
        """Test that custom image tag is accepted in query validation."""
        query = {
            "reco": "reco_config_content",
            "parton": None,
            "particle": None,
            "max_events": -1,
            "no_systematics": False,
            "no_filter": False,
            "image_tag": "v2.20.0_v0.2"
        }

        # This should not raise an exception
        generate_files_from_query(json.dumps(query), self.temp_dir)

    def test_image_tag_not_required(self):
        """Test that image_tag is optional and doesn't break existing queries."""
        query = {
            "reco": "reco_config_content",
            "parton": None,
            "particle": None,
            "max_events": -1,
            "no_systematics": False,
            "no_filter": False
        }

        # This should not raise an exception
        generate_files_from_query(json.dumps(query), self.temp_dir)

    def test_image_tag_none_allowed(self):
        """Test that None image tag is accepted."""
        query = {
            "reco": "reco_config_content",
            "parton": None,
            "particle": None,
            "max_events": -1,
            "no_systematics": False,
            "no_filter": False,
            "image_tag": None
        }

        # This should not raise an exception
        generate_files_from_query(json.dumps(query), self.temp_dir)

    def test_generated_files_created_with_image_tag(self):
        """Test that all expected files are generated when image_tag is present."""
        query = {
            "reco": "reco_config_content",
            "parton": None,
            "particle": None,
            "max_events": -1,
            "no_systematics": False,
            "no_filter": False,
            "image_tag": "v2.20.0_v0.2"
        }

        generate_files_from_query(json.dumps(query), self.temp_dir)

        # Check that reco.yaml is created
        reco_file = os.path.join(self.temp_dir, "reco.yaml")
        self.assertTrue(os.path.exists(reco_file))

        with open(reco_file, 'r') as f:
            content = f.read()
            self.assertEqual(content, "reco_config_content")

        # Check that generated_transformer.py is created
        transformer_file = os.path.join(self.temp_dir, "generated_transformer.py")
        self.assertTrue(os.path.exists(transformer_file))


if __name__ == '__main__':
    unittest.main()
