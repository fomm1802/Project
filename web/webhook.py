import hmac
import hashlib

from flask import Blueprint, request

from utils import handle_github_webhook


def create_webhook_blueprint(webhook_secret: str, logger) -> Blueprint:
    bp = Blueprint("webhook", __name__)

    @bp.post("/github-sync")
    def github_sync():
        sig = request.headers.get("X-Hub-Signature-256", "")

        if webhook_secret:
            mac = hmac.new(
                webhook_secret.encode(),
                request.data,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(f"sha256={mac}", sig):
                logger.warning("Webhook signature mismatch")
                return "Forbidden", 403

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            logger.warning("Invalid webhook payload")
            return "Bad Request", 400

        handle_github_webhook(payload)
        return "OK", 200

    return bp
