from servicex_app.decorators import admin_required
from servicex_app.web.dashboard import dashboard


@admin_required
def global_dashboard():
    return dashboard("global_dashboard.html", user_specific=False)
