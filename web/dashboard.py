import hmac
from typing import Callable, Optional

from flask import Blueprint, redirect, render_template, request, session, url_for

from utils import get_int_env
from .services import load_dashboard_rows, save_dashboard_config


def create_dashboard_blueprint(
    get_bot: Callable[[], Optional[object]],
    dashboard_password: str,
) -> Blueprint:
    bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

    def _is_logged_in() -> bool:
        return bool(session.get("dashboard_auth"))

    def _load_rows():
        active_bot = get_bot()
        return load_dashboard_rows(active_bot)

    @bp.route("/login", methods=["GET", "POST"])
    def login():
        if _is_logged_in():
            return redirect(url_for("dashboard.home"))

        if request.method == "POST":
            if not dashboard_password:
                return "DASHBOARD_PASSWORD is not configured in .env", 500

            password = (request.form.get("password") or "").strip()
            if hmac.compare_digest(password, dashboard_password):
                session["dashboard_auth"] = True
                return redirect(url_for("dashboard.home"))
            return render_template("dashboard_login.html", error="รหัสผ่านไม่ถูกต้อง")

        return render_template("dashboard_login.html", error=None)

    @bp.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("dashboard.login"))

    @bp.get("")
    def home():
        if not _is_logged_in():
            return redirect(url_for("dashboard.login"))

        active_bot = get_bot()
        return render_template(
            "dashboard_home.html",
            rows=_load_rows(),
            bot_ready=bool(active_bot and active_bot.is_ready()),
            bot_user=str(active_bot.user) if active_bot and active_bot.user else "N/A",
            saved=request.args.get("saved") == "1",
            invite_hub_channel_id=str(get_int_env("INVITE_HUB_CHANNEL_ID") or ""),
        )

    @bp.post("/save")
    def save():
        if not _is_logged_in():
            return redirect(url_for("dashboard.login"))

        guild_id = (request.form.get("guild_id") or "").strip()
        if not guild_id:
            return "missing guild_id", 400

        notify_raw = (request.form.get("notify_channel_id") or "").strip()
        join_here = (request.form.get("join_here_channel_name") or "").strip()
        exempt_channel_ids = request.form.getlist("exempt_channel_ids")
        save_dashboard_config(
            guild_id=guild_id,
            notify_raw=notify_raw,
            join_here=join_here,
            exempt_channel_ids=exempt_channel_ids,
            exempt_guild_enabled=request.form.get("exempt_guild") == "on",
        )

        return redirect(url_for("dashboard.home", saved=1))

    return bp
