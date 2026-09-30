from flask import render_template, current_app

from servicex_app.decorators import oauth_required
from servicex_app.resources.servicex_resource import ServiceXResource


@oauth_required
def transformation_request(id_: str):
    current_app.logger.debug(f"Got transformation request: {id_}")
    req = ServiceXResource.get_owned_request(id_)
    return render_template("transformation_request.html", req=req)
