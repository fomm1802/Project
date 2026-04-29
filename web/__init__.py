import os
from typing import Callable, Optional

from flask import Flask, jsonify, redirect
from werkzeug.middleware.proxy_fix import ProxyFix

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
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "true").lower() in ("1", "true", "yes", "on")

    trust_proxy = os.getenv("TRUST_PROXY", "true").lower() in ("1", "true", "yes", "on")
    if trust_proxy:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


    @app.get("/")
    def root_redirect():
        return redirect("/dashboard", code=302)

    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True}), 200

    app.register_blueprint(create_api_blueprint(get_bot))
    app.register_blueprint(create_dashboard_blueprint(get_bot, dashboard_password))
    app.register_blueprint(create_webhook_blueprint(webhook_secret, logger))

    return app
