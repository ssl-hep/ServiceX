from datetime import datetime

from flask import session, render_template, redirect, url_for, \
    request, flash, current_app

from servicex.models import db, UserModel
from servicex.decorators import oauth_required
from .forms import ProfileForm


@oauth_required
def edit_profile():
    sub = session.get('sub')
    user: UserModel = UserModel.find_by_sub(sub)
    form = ProfileForm()
    if request.method == 'GET':
        form = ProfileForm(user)
    elif request.method == 'POST':
        if form.validate_on_submit():
            user.name = form.name.data
            user.email = form.email.data
            user.institution = form.institution.data
            user.experiment = form.experiment.data
            user.updated_at = datetime.utcnow()
            db.session.commit()
            flash("Your profile has been saved!", 'success')
            current_app.logger.info(f"Updated profile for {user.name}")
            return redirect(url_for('profile'))
        else:
            current_app.logger.error(f"Edit Profile Form errors {form.errors}")
            flash("Profile could not be saved. Please fix invalid fields below.", 'danger')
    return render_template("profile_form.html", form=form, action="Edit Profile")
