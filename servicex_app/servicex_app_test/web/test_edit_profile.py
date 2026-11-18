from flask import Response, url_for

from .web_test_base import WebTestBase


class TestEditProfile(WebTestBase):
    module = "servicex_app.web.edit_profile"

    def test_get_edit_profile(self, client, user, captured_templates):
        with client.session_transaction() as sess:
            sess["sub"] = user.sub
        response: Response = client.get(url_for("edit_profile"))
        assert response.status_code == 200
        template, context = captured_templates[0]
        assert template.name == "profile_form.html"
        assert context["action"] == "Edit Profile"

    def test_post_edit_profile(self, client, user, db, mock_flash, mocker):
        mocker.patch("servicex_app.web.edit_profile.db", db)

        assert user.name != "new name"
        with client.session_transaction() as sess:
            sess["sub"] = "some-new-user-id"
        response: Response = client.post(
            url_for("edit_profile"),
            data={
                "name": "new name",
                "email": user.email,
                "institution": user.institution,
                "experiment": user.experiment,
            },
        )
        db.session.commit.assert_called_once()
        assert user.name == "new name"
        mock_flash.assert_called_once()
        assert "Your profile has been saved!" in mock_flash.call_args[0][0]
        assert response.status_code == 302
        assert response.location == url_for("profile")

    def test_get_edit_profile_email_read_only(self, client, user):
        with client.session_transaction() as sess:
            sess["sub"] = user.sub
            sess["email"] = user.email
        response: Response = client.get(url_for("edit_profile"))
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        email_input = next(line for line in html.splitlines() if 'id="email"' in line)
        assert "readonly" in email_input
        assert user.email in email_input

    def test_post_edit_profile_keeps_email(self, client, user, db, mock_flash, mocker):
        mocker.patch("servicex_app.web.edit_profile.db", db)
        original_email = user.email

        with client.session_transaction() as sess:
            sess["sub"] = user.sub
            sess["email"] = original_email
        response: Response = client.post(
            url_for("edit_profile"),
            data={
                "name": "new name",
                "email": "someone-else@example.com",
                "institution": "new institution",
                "experiment": user.experiment,
            },
        )
        assert response.status_code == 302
        db.session.commit.assert_called_once()
        assert user.email == original_email
        assert user.name == "new name"
        with client.session_transaction() as sess:
            assert sess["email"] == original_email
            assert sess["name"] == "new name"
            assert sess["institution"] == "new institution"

    def test_post_edit_profile_invalid(self, client, user, mock_flash):
        with client.session_transaction() as sess:
            sess["sub"] = user.sub
        response: Response = client.post(
            url_for("edit_profile"), data={"email": "invalid-email"}
        )
        assert response.status_code == 200
        mock_flash.assert_called_once()
        error_msg = "Profile could not be saved. Please fix invalid fields below."
        assert error_msg in mock_flash.call_args[0][0]
