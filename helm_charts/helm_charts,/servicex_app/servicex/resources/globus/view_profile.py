from flask import session, render_template, redirect, url_for
from sqlalchemy.orm.exc import NoResultFound

from servicex.models import UserModel
from .decorators import authenticated


@authenticated
def view_profile():
    globus_id = session.get('primary_identity')
    try:
        user = UserModel.find_by_globus_id(globus_id)
        return render_template('profile.html', user=user)
    except NoResultFound:
        return redirect(url_for('create_profile'))
