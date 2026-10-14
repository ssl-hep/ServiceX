from flask import Response, url_for
from pytest import fixture

from .web_test_base import WebTestBase


class TestUserDashboard(WebTestBase):

    @fixture
    def mock_query(self, mocker):
        mock_tr = mocker.patch("servicex_app.web.dashboard.TransformRequest")
        return mock_tr.query.filter_by.return_value.order_by.return_value

    def test_get_empty_state(self, client, user, mock_query, captured_templates):
        user.id = 42
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
        pagination = mock_query.paginate(page=1, per_page=15, total=0, items=[])
        mock_query.paginate.return_value = pagination
        response: Response = client.get(
            url_for("user-dashboard"), headers=self.fake_header()
        )
        assert response.status_code == 200
        template, context = captured_templates[0]
        assert template.name == "user_dashboard.html"
        assert context["pagination"] == pagination

    def test_get_without_user_id_in_session(
        self, client, user, mocker, captured_templates
    ):
        # auth is disabled, so nothing ever put a user_id in the session
        mock_tr = mocker.patch("servicex_app.web.dashboard.TransformRequest")
        mock_query = mock_tr.query.order_by.return_value
        pagination = mock_query.paginate(page=1, per_page=15, total=0, items=[])
        mock_query.paginate.return_value = pagination
        response: Response = client.get(
            url_for("user-dashboard"), headers=self.fake_header()
        )
        assert response.status_code == 200
        mock_tr.query.filter_by.assert_not_called()
        template, context = captured_templates[0]
        assert template.name == "user_dashboard.html"
        assert context["pagination"] == pagination

    def test_get_with_results(self, client, user, mock_query, captured_templates):
        user.id = 42
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
        items = [self._test_transformation_req(id=i + 1) for i in range(3)]
        pagination = mock_query.paginate(page=1, per_page=15, total=100, items=items)
        mock_query.paginate.return_value = pagination
        response: Response = client.get(
            url_for("user-dashboard"), headers=self.fake_header()
        )
        assert response.status_code == 200
        template, context = captured_templates[0]
        assert template.name == "user_dashboard.html"
        assert context["pagination"] == pagination
