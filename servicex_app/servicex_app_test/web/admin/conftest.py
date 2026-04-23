import os

import pytest


@pytest.fixture(autouse=True)
def set_allowed_image_prefixes():
    os.environ.setdefault("ALLOWED_IMAGE_PREFIXES", '["sslhep/"]')
