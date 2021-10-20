from servicex.decorators import admin_required
from servicex.web.dashboard import dashboard


@admin_required
def global_dashboard():
    return dashboard("global_dashboard.html", user_specific=False)
