import os
import time
import logging
import traceback
import asyncio
from threading import Thread
from typing import Optional

import psutil
import discord
from discord.ext import commands
from dotenv import load_dotenv
import coloredlogs

from utils import (
    async_get_server_config,
    async_full_sync,
    check_github_token,
)
from web import create_web_app


# ---------- Load .env ----------
load_dotenv()

raw = os.getenv("GITHUB_TOKEN")
GITHUB_TOKEN = (raw or "").strip().replace("\ufeff", "")

print("======== ENV DEBUG ========")
print("WORKING DIR :", os.getcwd())
print(".env token loaded :", bool(GITHUB_TOKEN))
print("TOKEN LENGTH :", len(GITHUB_TOKEN))
print("===========================")


# ---------- Logging ----------
coloredlogs.install(
    level=logging.INFO,
    fmt="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("discord_bot")


# ---------- Flask Server ----------
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "").strip()

bot: Optional["MyBot"] = None
app = create_web_app(
    get_bot=lambda: bot,
    dashboard_password=DASHBOARD_PASSWORD,
    webhook_secret=WEBHOOK_SECRET,
    logger=logger,
)


def run_flask():
    port = int(os.getenv("WEBHOOK_PORT", 12214))
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )


# ---------- Bot Presence Status ----------
async def update_bot_status(bot):
    await bot.wait_until_ready()

    process = psutil.Process()
    member_count_cache = 0
    member_count_refreshed_at = 0.0

    while not bot.is_closed():

        uptime = int(time.time() - bot.start_time)

        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60

        guild_count = len(bot.guilds)

        now = time.time()
        if (now - member_count_refreshed_at) >= 60:
            member_count_cache = sum((g.member_count or 0) for g in bot.guilds)
            member_count_refreshed_at = now

        total_members = member_count_cache

        cpu_usage = psutil.cpu_percent(interval=None)
        mem_mb = int(process.memory_info().rss / 1024 / 1024)

        status_text = (
            f"🟢 Online | {guild_count} Servers — "
            f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        )

        sys_info = (
            f"👥 {total_members} Members | "
            f"💻 CPU {cpu_usage:.0f}% | "
            f"🧠 {mem_mb}MB"
        )

        try:
            await bot.change_presence(
                activity=discord.CustomActivity(
                    name=f"{status_text} | {sys_info}"
                ),
                status=discord.Status.online
            )
        except Exception:
            pass

        await asyncio.sleep(10)


# ---------- Discord Bot ----------
PREFIX = os.getenv("BOT_PREFIX", "!")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.voice_states = True

COGS = [
    "cogs.commands.emoji_uploader",
    "cogs.commands.set_notify_channel",
    "cogs.commands.invite_all",
    "cogs.events.link_detection",
    "cogs.events.voice_events",
]


class MyBot(commands.AutoShardedBot):
    def __init__(self):
        super().__init__(command_prefix=PREFIX, intents=intents)
        self.start_time = time.time()
        self.status_task: Optional[asyncio.Task] = None

    async def setup_hook(self):
        for cog in COGS:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ โหลด {cog} สำเร็จ")
            except Exception:
                logger.error(traceback.format_exc())

        try:
            await self.tree.sync()
            logger.info("✅ ซิงค์ Slash Commands สำเร็จ")
        except:
            logger.error("❌ Sync คำสั่งล้มเหลว")

    async def on_ready(self):
        logger.info(f"👋 Logged in as {self.user} ({self.user.id})")

        await async_full_sync()

        for g in self.guilds:
            await async_get_server_config(g.id)

        logger.info("✅ Config sync เรียบร้อย")

        # Start realtime status updater once; prevent duplicates on reconnect.
        if not self.status_task or self.status_task.done():
            self.status_task = self.loop.create_task(update_bot_status(self))


# ---------- Entrypoint ----------
async def main():
    global bot

    token = os.getenv("DISCORD_TOKEN")

    if not token:
        logger.error("❌ ไม่มี DISCORD_TOKEN ใน .env")
        return

    has_token = check_github_token()

    if not has_token:
        logger.warning("⚠️ ไม่มี GITHUB_TOKEN: โหมด Local-Only")

    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

    bot = MyBot()

    try:
        await bot.start(token)
    except KeyboardInterrupt:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
