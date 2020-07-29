from flask import request, render_template, redirect, url_for, session, \
    flash

from servicex.models import UserModel
from .decorators import authenticated
from .forms import ProfileForm


@authenticated
def create_profile():
    form = ProfileForm()
    if request.method == 'GET':
        form = ProfileForm()
        form.name.data = session.get('name')
        form.email.data = session.get('email')
        form.institution.data = session.get('institution')
    elif request.method == 'POST':
        if form.validate_on_submit():
            new_user = UserModel(
                globus_id=session['primary_identity'],
                email=form.email.data,
                name=form.name.data,
                institution=form.institution.data,
                experiment=form.experiment.data)
            new_user.save_to_db()
            session['user_id'] = new_user.id
            session['admin'] = new_user.admin
            flash("Profile created! Your account is pending approval. "
                  "We'll email you when it's ready.",
                  'success')
            return redirect(url_for('profile'))
        else:
            print("Create Profile Form errors", form.errors)
            flash("Profile could not be saved. Please fix invalid fields below.", 'danger')
    return render_template("profile_form.html", form=form, action="Create Profile")
