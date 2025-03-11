from flask import redirect, url_for, session, flash, current_app
from flask_jwt_extended import create_refresh_token

from servicex_app.models import db, UserModel
from servicex_app.decorators import oauth_required


@oauth_required
def api_token():
    """Generate a new ServiceX refresh token."""
    email = session.get('email')
    user: UserModel = UserModel.find_by_email(email)
    user.refresh_token = create_refresh_token(email)
    db.session.commit()
    current_app.logger.info(f"Generated new API token for {email}")
    flash("Your new API token has been generated!", 'success')
    return redirect(url_for('profile'))
