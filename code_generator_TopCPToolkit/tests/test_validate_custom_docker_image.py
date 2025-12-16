import pytest
from pytest import MonkeyPatch
from servicex.TopCP_code_generator.request_translator import (
    validate_custom_docker_image,
)
from servicex_codegen.code_generator import GenerateCodeException


class TestValidateCustomDockerImage:
    """Tests for the validate_custom_docker_image function"""

    def test_validate_with_matching_prefix(self, monkeypatch: MonkeyPatch):
        monkeypatch.setenv(
            "ALLOWED_DOCKER_REGISTRIES",
            '{"docker.io": {"allowedImagePrefixes": ["sslhep/servicex_science_image_topcp:"]}}'
        )
        result = validate_custom_docker_image(
            "sslhep/servicex_science_image_topcp:2.17.0"
        )
        assert result is True

    def test_validate_with_multiple_prefixes(self, monkeypatch: MonkeyPatch):
        """Test validation with multiple allowed prefixes"""
        monkeypatch.setenv(
            "ALLOWED_DOCKER_REGISTRIES",
            '{"docker.io": {"allowedImagePrefixes": ["sslhep/custom:", "sslhep/servicex_science_image:"]}}'
        )
        assert (
            validate_custom_docker_image("sslhep/servicex_science_image:latest")
            is True
        )
        assert validate_custom_docker_image("sslhep/custom:v1") is True

    def test_validate_with_no_matching_prefix(self, monkeypatch: MonkeyPatch):
        """Test validation fails when image doesn't match any allowed prefix"""
        monkeypatch.setenv(
            "ALLOWED_DOCKER_REGISTRIES",
            '{"docker.io": {"allowedImagePrefixes": ["sslhep/servicex_science_image_topcp:"]}}'
        )
        with pytest.raises(GenerateCodeException, match="not allowed"):
            validate_custom_docker_image("unauthorized/image:latest")

    def test_validate_with_no_env_variable(self, monkeypatch: MonkeyPatch):
        """Test validation fails when ALLOWED_DOCKER_REGISTRIES is not set"""
        monkeypatch.delenv("ALLOWED_DOCKER_REGISTRIES")
        with pytest.raises(
            GenerateCodeException, match="Custom Docker images are not allowed."
        ):
            validate_custom_docker_image("sslhep/servicex_science_image_topcp:2.17.0")

    def test_validate_with_invalid_json(self, monkeypatch: MonkeyPatch):
        """Test validation fails with invalid JSON in env variable"""
        monkeypatch.setenv("ALLOWED_DOCKER_REGISTRIES", "not-valid-json")
        with pytest.raises(GenerateCodeException, match="improperly configured"):
            validate_custom_docker_image("sslhep/servicex_science_image_topcp:2.17.0")

    def test_validate_with_empty_list(self, monkeypatch: MonkeyPatch):
        """Test validation fails when allowed list is empty"""
        monkeypatch.setenv("ALLOWED_DOCKER_REGISTRIES", "[]")
        with pytest.raises(GenerateCodeException, match="not supported"):
            validate_custom_docker_image("sslhep/servicex_science_image_topcp:2.17.0")
