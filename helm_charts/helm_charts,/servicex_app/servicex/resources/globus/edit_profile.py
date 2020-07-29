from datetime import datetime

from flask import session, render_template, redirect, url_for, request, flash

from servicex.models import db, UserModel
from .decorators import authenticated
from .forms import ProfileForm


@authenticated
def edit_profile():
    globus_id = session.get('primary_identity')
    user: UserModel = UserModel.find_by_globus_id(globus_id)
    form = ProfileForm()
    if request.method == 'GET':
        form.name.data = user.name
        form.email.data = user.email
        form.institution.data = user.institution
        form.experiment.data = user.experiment
    elif request.method == 'POST':
        if form.validate_on_submit():
            user.name = form.name.data
            user.email = form.email.data
            user.institution = form.institution.data
            user.experiment = form.experiment.data
            user.updated_at = datetime.utcnow()
            db.session.commit()
            flash("Your profile has been saved!", 'success')
            return redirect(url_for('profile'))
        else:
            print("Edit Profile Form errors", form.errors)
            flash("Profile could not be saved. Please fix invalid fields below.", 'danger')
    return render_template("profile_form.html", form=form, action="Edit Profile")
