from flask import session, render_template, redirect, url_for

from servicex_app.models import UserModel
from servicex_app.decorators import oauth_required


@oauth_required
def view_profile():
    email = session.get('email')
    user = UserModel.find_by_email(email)
    if not user:
        return redirect(url_for('create_profile'))
    return render_template('profile.html', user=user)
