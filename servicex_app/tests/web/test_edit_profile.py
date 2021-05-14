from flask import Response, url_for

from .web_test_base import WebTestBase


class TestEditProfile(WebTestBase):
    module = "servicex.web.edit_profile"

    def test_get_edit_profile(self, client, user, captured_templates):
        with client.session_transaction() as sess:
            sess['sub'] = user.sub
        response: Response = client.get(url_for('edit_profile'))
        assert response.status_code == 200
        template, context = captured_templates[0]
        assert template.name == "profile_form.html"
        assert context["action"] == "Edit Profile"

    def test_post_edit_profile(self, client, user, db, mock_flash):
        assert user.name != 'new name'
        with client.session_transaction() as sess:
            sess['sub'] = 'some-new-user-id'
        response: Response = client.post(url_for('edit_profile'), data={
            'name': 'new name',
            'email': user.email,
            'institution': user.institution,
            'experiment': user.experiment
        })
        assert db.session.commit.called_once()
        assert user.name == 'new name'
        mock_flash.assert_called_once()
        assert "Your profile has been saved!" in mock_flash.call_args[0][0]
        assert response.status_code == 302
        assert response.location == url_for('profile', _external=True)

    def test_post_edit_profile_invalid(self, client, user, mock_flash):
        with client.session_transaction() as sess:
            sess['sub'] = user.sub
        response: Response = client.post(url_for('edit_profile'), data={
            'email': 'invalid-email'
        })
        assert response.status_code == 200
        mock_flash.assert_called_once()
        error_msg = "Profile could not be saved. Please fix invalid fields below."
        assert error_msg in mock_flash.call_args[0][0]
