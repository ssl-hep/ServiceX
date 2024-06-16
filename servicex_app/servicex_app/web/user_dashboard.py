from servicex_app.decorators import oauth_required
from servicex_app.web.dashboard import dashboard


@oauth_required
def user_dashboard():
    return dashboard("user_dashboard.html", user_specific=True)
