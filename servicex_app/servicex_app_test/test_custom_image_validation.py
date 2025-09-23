"""Test custom image tag validation for TopCP transformations."""

import json
import unittest
from werkzeug.exceptions import BadRequest

from servicex_app.resources.transformation.submit import (
    validate_custom_image_tag,
    SubmitTransformationRequest,
)


class TestCustomImageValidation(unittest.TestCase):

    def setUp(self):
        self.config = {
            "TOPCP_ALLOWED_REPOSITORIES": [
                "sslhep/servicex_science_image_topcp",
                "registry.gitlab.com/topcp-project/toolkit",
            ],
            "TOPCP_IMAGE_TAG_PATTERN": r"^v?\d+\.\d+\.\d+[-_]v?\d+\.\d+$",
            "TOPCP_DEFAULT_BASE_IMAGE": "sslhep/servicex_science_image_topcp",
        }

    def test_valid_image_tag_format(self):
        """Test that valid image tag formats are accepted."""
        test_cases = ["v2.20.0_v0.2", "2.20.0_v0.2", "v1.15.0-v1.0", "3.0.0_v2.5"]

        for tag in test_cases:
            with self.subTest(tag=tag):
                image, result_tag = validate_custom_image_tag(tag, self.config, "topcp")
                self.assertEqual(image, "sslhep/servicex_science_image_topcp")
                self.assertEqual(result_tag, tag)

    def test_invalid_image_tag_format(self):
        """Test that invalid image tag formats are rejected."""
        test_cases = [
            "latest",
            "2.20.0",
            "v2.20.0",
            "invalid-tag",
            "v2.20.0_v0.2.1",  # Too many version components
            "2.20_v0.2",  # Missing patch version
        ]

        for tag in test_cases:
            with self.subTest(tag=tag):
                with self.assertRaises(BadRequest):
                    validate_custom_image_tag(tag, self.config, "topcp")

    def test_non_topcp_codegen_returns_none(self):
        """Test that non-TopCP code generators return None."""
        image, tag = validate_custom_image_tag("v2.20.0_v0.2", self.config, "uproot")
        self.assertIsNone(image)
        self.assertIsNone(tag)

    def test_empty_image_tag_returns_none(self):
        """Test that empty image tag returns None."""
        test_cases = [None, "", " "]

        for tag in test_cases:
            with self.subTest(tag=tag):
                image, result_tag = validate_custom_image_tag(tag, self.config, "topcp")
                self.assertIsNone(image)
                self.assertIsNone(result_tag)

    def test_missing_config_uses_defaults(self):
        """Test that missing configuration uses default values."""
        minimal_config = {}

        image, tag = validate_custom_image_tag("v2.20.0_v0.2", minimal_config, "topcp")
        self.assertEqual(image, "sslhep/servicex_science_image_topcp")
        self.assertEqual(tag, "v2.20.0_v0.2")

    def test_repository_validation_success(self):
        """Test that repository validation passes when default image is in allowed repos."""
        config = {
            "TOPCP_ALLOWED_REPOSITORIES": [
                "sslhep/servicex_science_image_topcp",
                "registry.gitlab.com/topcp-project/toolkit",
            ],
            "TOPCP_DEFAULT_BASE_IMAGE": "sslhep/servicex_science_image_topcp",
        }

        image, tag = validate_custom_image_tag("v2.20.0_v0.2", config, "topcp")
        self.assertEqual(image, "sslhep/servicex_science_image_topcp")
        self.assertEqual(tag, "v2.20.0_v0.2")

    def test_repository_validation_failure(self):
        """Test that repository validation fails when default image is not in allowed repos."""
        config = {
            "TOPCP_ALLOWED_REPOSITORIES": [
                "registry.gitlab.com/topcp-project/toolkit",
            ],
            "TOPCP_DEFAULT_BASE_IMAGE": "sslhep/servicex_science_image_topcp",
        }

        with self.assertRaises(BadRequest):
            validate_custom_image_tag("v2.20.0_v0.2", config, "topcp")


class TestImageTagExtraction(unittest.TestCase):

    def setUp(self):
        self.submit_request = SubmitTransformationRequest()

    def test_extract_image_tag_from_topcp_query(self):
        """Test extraction of image tag from TopCP query."""
        query = {
            "reco": "reco_config",
            "parton": None,
            "particle": None,
            "max_events": -1,
            "no_systematics": False,
            "no_filter": False,
            "image_tag": "v2.20.0_v0.2",
        }

        result = self.submit_request._extract_custom_image_tag(
            json.dumps(query), "topcp"
        )
        self.assertEqual(result, "v2.20.0_v0.2")

    def test_extract_image_tag_missing_returns_none(self):
        """Test that missing image tag returns None."""
        query = {
            "reco": "reco_config",
            "parton": None,
            "particle": None,
            "max_events": -1,
            "no_systematics": False,
            "no_filter": False,
        }

        result = self.submit_request._extract_custom_image_tag(
            json.dumps(query), "topcp"
        )
        self.assertIsNone(result)

    def test_extract_image_tag_non_topcp_returns_none(self):
        """Test that non-TopCP codegen returns None."""
        query = {"selection": "some_selection", "image_tag": "v2.20.0_v0.2"}

        result = self.submit_request._extract_custom_image_tag(
            json.dumps(query), "uproot"
        )
        self.assertIsNone(result)

    def test_extract_image_tag_invalid_json_returns_none(self):
        """Test that invalid JSON returns None."""
        invalid_json = "{ invalid json }"

        result = self.submit_request._extract_custom_image_tag(invalid_json, "topcp")
        self.assertIsNone(result)

    def test_extract_image_tag_none_value(self):
        """Test that None image tag value is returned as None."""
        query = {"reco": "reco_config", "image_tag": None}

        result = self.submit_request._extract_custom_image_tag(
            json.dumps(query), "topcp"
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
