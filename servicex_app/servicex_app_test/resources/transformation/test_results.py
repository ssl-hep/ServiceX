from pytest import fixture
from datetime import datetime, timedelta

from servicex_app.code_gen_adapter import CodeGenAdapter
from servicex_app_test.resource_test_base import ResourceTestBase
from servicex_app.models import TransformationResult


class TestTransformationResults(ResourceTestBase):
    @staticmethod
    def _generate_transformation_request(**kwargs):
        request = {
            "did": "123-45-678",
            "selection": "test-string",
            "result-destination": "object-store",
            "result-format": "root-file",
            "workers": 10,
            "codegen": "atlasxaod",
        }
        request.update(kwargs)
        return request

    @fixture
    def mock_codegen(self, mocker):
        mock_code_gen = mocker.MagicMock(CodeGenAdapter)
        mock_code_gen.generate_code_for_selection.return_value = (
            "my-cm",
            "sslhep/func_adl:latest",
            "bash",
            "echo",
        )
        return mock_code_gen

    @fixture
    def mock_transformation_result(self, mocker):
        mock = mocker.patch(
            "servicex_app.resources.transformation.results.TransformationResult"
        )
        mock.to_json_list.side_effect = TransformationResult.to_json_list
        return mock

    @staticmethod
    def sample_results():
        """Return a list of sample transformation results"""
        results = []
        base_time = datetime.utcnow()

        for i in range(3):
            result = TransformationResult(
                id=i + 1,
                file_id=i + 1,
                file_path=f"/output/result_{i}.root",
                request_id="test-request-id",
                transform_status="complete",
                transform_time=120 + (i * 10),
                total_events=1000 * (i + 1),
                total_bytes=2048 * (i + 1),
                avg_rate=10.5 + i,
                s3_object_name=f"bucket/result_{i}.root",
                created_at=base_time - timedelta(minutes=i * 10),
            )
            results.append(result)

        return results

    def test_get_results_nonexistent_request_id(self, mock_codegen, mock_celery_app):
        """Test getting results for non-existent request_id."""
        client = self._test_client(
            code_gen_service=mock_codegen,
            celery_app=mock_celery_app,
        )

        response = client.get("/servicex/transformation/non-existent-id/results")

        assert response.status_code == 200
        data = response.json

        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 0

    def test_get_results_missing_request_id(self, mock_codegen, mock_celery_app):
        """Test getting results with missing request_id parameter."""
        client = self._test_client(
            code_gen_service=mock_codegen,
            celery_app=mock_celery_app,
        )

        response = client.get("/servicex/transformation/results")

        assert response.status_code == 404

    def test_get_results_with_samples(
        self,
        mock_codegen,
        mock_celery_app,
        mock_transformation_result,
    ):
        """Test getting results with mock sample results."""
        client = self._test_client(
            code_gen_service=mock_codegen,
            celery_app=mock_celery_app,
        )

        mock_query = mock_transformation_result.query
        mock_filtered = mock_query.filter_by.return_value
        sample_results = self.sample_results()
        mock_filtered.__iter__ = lambda mock_self: iter(sample_results)

        response = client.get("/servicex/transformation/test-request-id/results")

        assert response.status_code == 200
        data = response.json

        assert "results" in data
        assert isinstance(data["results"], list)
        assert (
            len(data["results"]) == 3
        )  # We expect 3 results from our sample_results function

        result = data["results"][0]
        assert "request-id" in result
        assert "file-path" in result
        assert "transform_status" in result
        assert "transform_time" in result
        assert "total-events" in result
        assert "total-bytes" in result
        assert "avg-rate" in result

        mock_query.filter_by.assert_called_with(request_id="test-request-id")

    def test_get_results_with_invalid_later_than_format(
        self, mock_codegen, mock_celery_app
    ):
        """Test later_than parameter with invalid datetime format."""
        client = self._test_client(
            code_gen_service=mock_codegen,
            celery_app=mock_celery_app,
        )

        response = client.get(
            "/servicex/transformation/any-request-id/results",
            query_string={"later_than": "invalid-datetime-format"},
        )

        assert response.status_code == 400
        data = response.json

        assert "message" in data
        assert (
            "later_than value invalid-datetime-format is not an ISO 8601 compliant datetime"
            in data["message"]
        )
