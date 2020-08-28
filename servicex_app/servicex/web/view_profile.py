from flask import session, render_template, redirect, url_for

from servicex.models import UserModel
from servicex.decorators import oauth_required


@oauth_required
def view_profile():
    sub = session.get('sub')
    user = UserModel.find_by_sub(sub)
    if not user:
        return redirect(url_for('create_profile'))
    return render_template('profile.html', user=user)
