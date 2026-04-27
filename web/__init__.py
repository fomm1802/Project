import os
from typing import Callable, Optional

from flask import Flask

from .api import create_api_blueprint
from .dashboard import create_dashboard_blueprint
from .webhook import create_webhook_blueprint


def create_web_app(
    get_bot: Callable[[], Optional[object]],
    dashboard_password: str,
    webhook_secret: str,
    logger,
) -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.secret_key = os.getenv("DASHBOARD_SECRET_KEY", "").strip() or os.urandom(32)

    app.register_blueprint(create_api_blueprint(get_bot))
    app.register_blueprint(create_dashboard_blueprint(get_bot, dashboard_password))
    app.register_blueprint(create_webhook_blueprint(webhook_secret, logger))

    return app
