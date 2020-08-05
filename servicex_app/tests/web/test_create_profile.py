from flask import Response, url_for, render_template, get_flashed_messages

from .web_test_base import WebTestBase


class TestCreateProfile(WebTestBase):
    def test_get_create_profile(self, client):
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
        assert response.data.decode() == render_template('profile_form.html',
                                                         action='Create Profile',
                                                         form=form)

    def test_post_create_profile(self, client, new_user, db):
        with client.session_transaction() as sess:
            sess['sub'] = 'create-me'
        data = {
            'name': 'Jane Doe',
            'email': 'jane@example.com',
            'institution': 'UChicago',
            'experiment': 'ATLAS'
        }
        response: Response = client.post(url_for('create_profile'), data=data)
        assert db.session.commit.called_once()
        assert new_user.save_to_db.called_once()
        success_msg = "Profile created!"
        assert success_msg in get_flashed_messages()[0]
        assert response.status_code == 302
        assert response.location == url_for('profile', _external=True)

    def test_post_create_profile_invalid(self, client):
        with client.session_transaction() as sess:
            sess['sub'] = 'create-me'
        response: Response = client.post(url_for('create_profile'), data={
            'email': 'invalid-email'
        })
        assert response.status_code == 200
        error_msg = "Profile could not be saved. Please fix invalid fields below."
        assert error_msg in get_flashed_messages()
