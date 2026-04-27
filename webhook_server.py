from flask import Flask, request
import hmac, hashlib, os, logging
from utils import handle_github_webhook

app = Flask(__name__)
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")

@app.route("/github-sync", methods=["POST"])
def github_sync():
    if WEBHOOK_SECRET:
        sig = request.headers.get("X-Hub-Signature-256", "")
        mac = hmac.new(WEBHOOK_SECRET.encode(), request.data, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(f"sha256={mac}", sig):
            logging.warning("⚠️ GitHub Webhook signature mismatch")
            return "Forbidden", 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        logging.warning("⚠️ GitHub Webhook payload is empty or invalid")
        return "Bad Request", 400
    handle_github_webhook(payload)
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("WEBHOOK_PORT", 5000)))
