import os
import json
import time
import base64
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import asyncio
from typing import Dict, Any
from dotenv import dotenv_values


# ========= ENV + TOKEN LOADER =========

ENV_FILE = dotenv_values(".env")


def _get_env(key: str, fallback: str | None = None):
    """Universal ENV getter (Panel → OS Env → .env → fallback)"""
    return (
        os.getenv(key) or
        ENV_FILE.get(key) or
        fallback
    )


# GitHub repo config (defaults to your repo)
GITHUB_REPO   = _get_env("GITHUB_REPO",   "fomm1802/Bot")
GITHUB_BRANCH = _get_env("GITHUB_BRANCH", "main")


# ----- token sources priority -----
RAW_TOKEN = (
    _get_env("GITHUB_TOKEN")           # normal var

    or _get_env("GIT_ACCESS_TOKEN")    # Wispbyte panel
    or _get_env("GIT_ACCESS_TOKEN_SECRET")
    or _get_env("ACCESS_TOKEN")

    or _get_env("GH_TOKEN")            # fallback aliases

    or ""
).strip().replace("\ufeff", "")

GITHUB_TOKEN = RAW_TOKEN if RAW_TOKEN else None


LOCAL_CACHE: dict[str, dict] = {}

HTTP_TIMEOUT = (5, 20)
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/vnd.github+json"})
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=0.4, status_forcelist=[429,500,502,503,504], allowed_methods=["GET", "PUT"])))

REMOTE_SHA: dict[str, str] = {}
LAST_SYNC: dict[str, float] = {}


# ========= HTTP HELPERS =========

def _headers():
    if not GITHUB_TOKEN:
        return {}

    return {"Authorization": f"Bearer {GITHUB_TOKEN}"}


def _file_url(gid: str):
    return (
        f"https://api.github.com/repos/{GITHUB_REPO}"
        f"/contents/configs/{gid}.json?ref={GITHUB_BRANCH}"
    )


def _folder_url():
    return (
        f"https://api.github.com/repos/{GITHUB_REPO}"
        f"/contents/configs?ref={GITHUB_BRANCH}"
    )


def _local_path(gid: str):
    return f"configs/{gid}.json"


# ========= LOCAL CACHE =========

def _write_local(gid: str, conf: Dict[str, Any]):
    os.makedirs("configs", exist_ok=True)

    with open(_local_path(gid), "w", encoding="utf-8") as f:
        json.dump(conf, f, indent=2, ensure_ascii=False)

    LOCAL_CACHE[gid] = conf
    LAST_SYNC[gid] = time.time()


def _read_local(gid: str):
    path = _local_path(gid)

    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            LOCAL_CACHE[gid] = data
            return data

    except Exception as e:
        logging.error(f"อ่านไฟล์ local ล้มเหลว: {e}")
        return None


# ========= REMOTE FETCH =========

def _fetch_remote(gid: str):
    if not GITHUB_TOKEN:
        logging.info("ℹ️ ไม่มี GITHUB_TOKEN — ใช้ Local Mode")
        return None

    url = _file_url(gid)
    r = SESSION.get(url, headers=_headers(), timeout=HTTP_TIMEOUT)

    # error cases
    if r.status_code == 404:
        logging.warning(f"⚠️ ไม่พบไฟล์บน GitHub: configs/{gid}.json")
        return None

    if r.status_code == 401:
        logging.error("❌ Token ไม่มีสิทธิ์ (401 Unauthorized)")
        return None

    if r.status_code == 403:
        logging.error("❌ GitHub API ถูกบล็อก (403 Forbidden หรือ Rate-limit)")
        return None

    if r.status_code != 200:
        logging.error(f"❌ GitHub response: {r.status_code} {r.text}")
        return None

    info = r.json()
    REMOTE_SHA[gid] = info.get("sha")

    try:
        decoded = base64.b64decode(info["content"]).decode()
        data = json.loads(decoded)

        _write_local(gid, data)
        return data

    except Exception as e:
        logging.error(f"โหลด remote config fail: {e}")
        return None


# ========= PUBLIC CONFIG API =========

def get_server_config(gid: int | str):
    gid = str(gid)

    # throttle cache (10s)
    if gid in LOCAL_CACHE and time.time() - LAST_SYNC.get(gid, 0) < 10:
        return LOCAL_CACHE[gid]

    remote = _fetch_remote(gid)
    if remote:
        return remote

    local = _read_local(gid)
    if local:
        return local

    # default config
    conf = {
        "notify_channel_id": None,
        "join_here_channel_name": None,
        "exempt_channels": [],
        "exempt_guild": False,
    }

    _write_local(gid, conf)
    return conf


def save_server_config(gid: int | str, conf: Dict[str, Any]):
    gid = str(gid)

    _write_local(gid, conf)

    if not GITHUB_TOKEN:
        logging.info("ℹ️ ไม่มี GITHUB_TOKEN — บันทึกเฉพาะ Local")
        return

    payload = {
        "message": f"update {gid}.json",
        "content": base64.b64encode(
            json.dumps(conf, ensure_ascii=False, indent=2).encode()
        ).decode(),
        "branch": GITHUB_BRANCH,
    }

    if gid in REMOTE_SHA:
        payload["sha"] = REMOTE_SHA[gid]

    r = SESSION.put(_file_url(gid), headers=_headers(), json=payload, timeout=HTTP_TIMEOUT)

    if r.status_code in (200, 201):
        REMOTE_SHA[gid] = r.json()["content"]["sha"]
        logging.info(f"✅ sync {gid}.json ไป GitHub สำเร็จ")
    else:
        logging.error(f"❌ sync {gid}.json ล้มเหลว: {r.text}")


# ========= GITHUB WEBHOOK =========

def handle_github_webhook(payload: dict):
    if "commits" not in payload:
        return

    changed_files = set()
    for commit in payload.get("commits", []):
        for key in ("added", "modified"):
            for file_path in commit.get(key, []):
                changed_files.add(file_path)

    for f in changed_files:
        if f.startswith("configs/") and f.endswith(".json"):
            gid = os.path.basename(f).split(".")[0]
            logging.info(f"🔄 webhook: {gid}.json ถูกแก้ — ดึงใหม่")
            _fetch_remote(gid)


# ========= FULL SYNC =========

def full_sync():
    if not GITHUB_TOKEN:
        logging.info("ℹ️ Local-Only Mode — full_sync ข้าม")
        return

    r = SESSION.get(_folder_url(), headers=_headers(), timeout=HTTP_TIMEOUT)

    if r.status_code == 404:
        logging.error("❌ ไม่พบโฟลเดอร์ configs บน GitHub")
        logging.error(f"repo={GITHUB_REPO} branch={GITHUB_BRANCH}")
        return

    if r.status_code != 200:
        logging.error(f"❌ Full sync ล้มเหลว: {r.status_code} {r.text}")
        return

    count = 0

    for f in r.json():
        if f["name"].endswith(".json"):
            gid = f["name"].split(".")[0]
            if _fetch_remote(gid):
                count += 1

    logging.info(f"✅ Full sync เสร็จ — ดาวน์โหลด {count} ไฟล์")


# ========= ASYNC WRAPPERS =========

async def async_get_server_config(gid):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_server_config, gid)


async def async_save_server_config(gid, conf):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, save_server_config, gid, conf)


async def async_full_sync():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, full_sync)


# ========= TOKEN CHECK =========

def check_github_token():
    if not GITHUB_TOKEN:
        logging.info("ℹ️ ไม่มี GITHUB_TOKEN — Local Mode")
        return False

    r = SESSION.get(_folder_url(), headers=_headers(), timeout=HTTP_TIMEOUT)

    if r.status_code == 200:
        logging.info("✅ GITHUB_TOKEN ใช้งานได้ (configs folder OK)")
        return True

    if r.status_code == 404:
        logging.error("❌ repo / branch / configs path ไม่ตรง (404)")
        logging.error(f"repo={GITHUB_REPO} branch={GITHUB_BRANCH}")
        return False

    logging.error(f"❌ ตรวจสอบ token ล้มเหลว: {r.status_code}")
    return False


# ========= EXTRA HELPER =========

def get_int_env(name: str, default: int | None = None) -> int | None:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)

    except ValueError:
        logging.warning(f"⚠️ ENV {name} ไม่ใช่ตัวเลข: {value}")
        return default
