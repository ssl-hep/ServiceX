from flask import Response, url_for
from pytest import fixture

from .web_test_base import WebTestBase


class TestCreateProfile(WebTestBase):
    module = "servicex.web.create_profile"

    @fixture
    def new_user(self, mocker):
        mock = mocker.patch(f'{self.module}.UserModel').return_value
        mock.id = 2
        mock.name = 'Jane Doe'
        mock.email = 'jane@example.com'
        mock.institution = 'UChicago'
        mock.experiment = 'ATLAS'
        mock.pending = True
        mock.admin = False
        return mock

    def test_get_create_profile(self, client, captured_templates):
        with client.session_transaction() as sess:
            sess['name'] = 'Jane Doe'
            sess['email'] = 'jane@example.com'
            sess['institution'] = 'UChicago'
        from servicex.web.forms import ProfileForm
        form = ProfileForm()
        form.name.data = 'Jane Doe'
        form.email.data = 'jane@example.com'
        form.institution.data = 'UChicago'
        response: Response = client.get(url_for('create_profile'))
        assert response.status_code == 200
        template, context = captured_templates[0]
        assert template.name == "profile_form.html"
        assert context["action"] == "Create Profile"

    def test_post_create_profile(self, new_user, db, client, mock_flash):
        with client.session_transaction() as sess:
            sess['sub'] = 'create-me'
        keys = ['name', 'email', 'institution', 'experiment']
        data = {key: new_user.__dict__[key] for key in keys}
        response: Response = client.post(url_for('create_profile'), data=data)
        assert db.session.commit.called_once()
        assert new_user.save_to_db.called_once()
        mock_flash.assert_called_once()
        assert "Profile created!" in mock_flash.call_args[0][0]
        assert response.status_code == 302
        assert response.location == url_for('profile', _external=True)

    def test_post_create_profile_invalid(self, client, mock_flash):
        with client.session_transaction() as sess:
            sess['sub'] = 'create-me'
        response: Response = client.post(url_for('create_profile'), data={
            'email': 'invalid-email'
        })
        assert response.status_code == 200
        mock_flash.assert_called_once()
        error_msg = "Profile could not be saved. Please fix invalid fields below."
        assert error_msg in mock_flash.call_args[0][0]
