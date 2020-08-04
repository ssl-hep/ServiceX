from flask import redirect, url_for, session, flash

from servicex.models import db, UserModel, generate_api_key
from .decorators import authenticated


@authenticated
def api_key():
    """Generate a new ServiceX API key."""
    globus_id = session.get('primary_identity')
    user: UserModel = UserModel.find_by_globus_id(globus_id)
    user.api_key = generate_api_key()
    db.session.commit()
    flash("Your new API key has been generated!", 'success')
    return redirect(url_for('profile'))
