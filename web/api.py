import time
from typing import Callable, Optional

from flask import Blueprint, jsonify


def create_api_blueprint(get_bot: Callable[[], Optional[object]]) -> Blueprint:
    bp = Blueprint("api", __name__)

    @bp.get("/")
    def index():
        bot = get_bot()
        if not bot or not bot.is_ready():
            return jsonify({"online": False})

        uptime = int(time.time() - bot.start_time)
        return jsonify(
            {
                "online": True,
                "user": str(bot.user),
                "guilds": len(bot.guilds),
                "latency_ms": round(bot.latency * 1000),
                "uptime_sec": uptime,
            }
        )

    return bp
