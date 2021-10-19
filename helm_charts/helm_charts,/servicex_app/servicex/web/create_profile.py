import requests
from flask import request, render_template, redirect, url_for, session, \
    current_app, flash
from flask_jwt_extended import create_refresh_token

from servicex.models import UserModel
from servicex.decorators import oauth_required
from .forms import ProfileForm
from .slack_msg_builder import signup


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
                new_user.save_to_db()
                session['user_id'] = new_user.id
                session['admin'] = new_user.admin
                webhook_url = current_app.config.get("SIGNUP_WEBHOOK_URL")
                msg_segments = ["Profile created!"]
                if webhook_url and new_user.pending:
                    res = requests.post(webhook_url, signup(new_user.email))
                    # Raise exception on error (e.g. bad request or forbidden url)
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
