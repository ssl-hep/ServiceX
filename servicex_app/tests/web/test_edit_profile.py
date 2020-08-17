from flask import Response, url_for, render_template, get_flashed_messages

from .web_test_base import WebTestBase


class TestEditProfile(WebTestBase):
    def test_get_edit_profile(self, client, user):
        with client.session_transaction() as sess:
            sess['sub'] = user.sub
        response: Response = client.get(url_for('edit_profile'))
        assert response.status_code == 200
        from servicex.web.forms import ProfileForm
        form = ProfileForm(user)
        assert response.data.decode() == render_template('profile_form.html',
                                                         form=form,
                                                         action='Edit Profile')

    def test_post_edit_profile(self, client, user, db):
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
        success_msg = "Your profile has been saved!"
        assert success_msg in get_flashed_messages()
        assert response.status_code == 302
        assert response.location == url_for('profile', _external=True)

    def test_post_edit_profile_invalid(self, client, user):
        with client.session_transaction() as sess:
            sess['sub'] = user.sub
        response: Response = client.post(url_for('edit_profile'), data={
            'email': 'invalid-email'
        })
        assert response.status_code == 200
        error_msg = "Profile could not be saved. Please fix invalid fields below."
        assert error_msg in get_flashed_messages()
