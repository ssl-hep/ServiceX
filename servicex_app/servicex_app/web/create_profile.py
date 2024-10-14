import requests
from flask import request, render_template, redirect, url_for, session, \
    current_app, flash
from flask_jwt_extended import create_refresh_token

from servicex_app.models import UserModel
from servicex_app.decorators import oauth_required
from .forms import ProfileForm
from .slack_msg_builder import signup
from ..reliable_requests import servicex_retry, request_timeout


@servicex_retry()
def post_signup(webhook_url=None, signup_data=None):
    res = requests.post(webhook_url,
                        signup_data,
                        timeout=request_timeout)
    return res


@oauth_required
def create_profile():
    form = ProfileForm()
    if request.method == 'GET':
        form = ProfileForm()
        form.name.data = session.get('name')
        form.email.data = session.get('email')
        form.institution.data = session.get('institution')
    elif request.method == 'POST':
        if form.validate_on_submit():
            sub = session['sub']
            new_user = UserModel(
                sub=sub,
                email=form.email.data,
                name=form.name.data,
                institution=form.institution.data,
                experiment=form.experiment.data,
                refresh_token=create_refresh_token(identity=sub))
            if new_user.email == current_app.config.get('JWT_ADMIN'):
                new_user.admin = True
                new_user.pending = False
            try:
                check_user_email = UserModel.find_by_email(form.email.data)
                if check_user_email and not check_user_email.refresh_token:
                    UserModel.update_refresh_token_by_email(check_user_email.email, create_refresh_token(identity=sub),
                                                            False)
                    new_user.pending = False
                else:
                    new_user.save_to_db()
                session['user_id'] = new_user.id
                session['admin'] = new_user.admin
                webhook_url = current_app.config.get("SIGNUP_WEBHOOK_URL")
                msg_segments = ["Profile created!"]
                if webhook_url and new_user.pending:
                    res = post_signup(webhook_url, signup(new_user.email))
                    res.raise_for_status()
                    msg_segments += ["Your account is pending approval.",
                                     "We'll email you when it's ready."]
                current_app.logger.info(f"Created profile for {new_user.id}")
                flash(' '.join(msg_segments), 'success')
                return redirect(url_for('profile'))
            except requests.exceptions.HTTPError as err:
                current_app.logger.error(f"Error in response from Slack webhook: {err}")
        else:
            current_app.logger.error(f"Create Profile Form error: {form.errors}")
            flash("Profile could not be saved. Please fix invalid fields below.", 'danger')
    return render_template("profile_form.html", form=form, action="Create Profile")
