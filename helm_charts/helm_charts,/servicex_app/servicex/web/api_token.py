from flask import redirect, url_for, session, flash, current_app
from flask_jwt_extended import create_refresh_token

from servicex.models import db, UserModel
from servicex.decorators import oauth_required


@oauth_required
def api_token():
    """Generate a new ServiceX refresh token."""
    sub = session.get('sub')
    user: UserModel = UserModel.find_by_sub(sub)
    user.refresh_token = create_refresh_token(sub)
    db.session.commit()
    current_app.logger.info(f"Generated new API token for {sub}")
    flash("Your new API token has been generated!", 'success')
    return redirect(url_for('profile'))
