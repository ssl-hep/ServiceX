from servicex.decorators import oauth_required
from servicex.web.dashboard import dashboard


@oauth_required
def user_dashboard():
    return dashboard("user_dashboard.html", user_specific=True)
