import os
import time
import asyncio
import datetime
from io import BytesIO
import discord
from discord.ext import commands, tasks
from discord import app_commands
from utils import get_int_env


# ---------- VIEW BUTTONS ----------
class InviteRefreshButton(discord.ui.View):
    def __init__(self, cog, invites_text: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.invites_text = invites_text

    # ------- REFRESH NOW -------
    @discord.ui.button(
        label="Refresh Now",
        emoji="🔁",
        style=discord.ButtonStyle.green
    )
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ เฉพาะผู้ดูแลเท่านั้นที่ใช้ปุ่มนี้ได้",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        await self.cog.run_sync_task(manual=True)

        await interaction.followup.send(
            "✅ ซิงก์สำเร็จแล้ว",
            ephemeral=True
        )

    # ------- COPY ALL INVITES -------
    @discord.ui.button(
        label="Copy All Invites",
        emoji="📋",
        style=discord.ButtonStyle.blurple
    )
    async def copy_all(self, interaction: discord.Interaction, button: discord.ui.Button):

        text = self.invites_text or "(ไม่มีข้อมูล invite)"

        if len(text) <= 1800:
            await interaction.response.send_message(
                f"📨 **รายการ Invite ทั้งหมด**\n```\n{text}\n```",
                ephemeral=True
            )
            return

        file_buffer = BytesIO(text.encode("utf-8"))
        await interaction.response.send_message(
            "📨 รายการ Invite ยาวเกินข้อความ Discord — ส่งเป็นไฟล์แทน",
            ephemeral=True,
            file=discord.File(file_buffer, filename="invite-list.txt")
        )


# ---------- MAIN COG ----------
class InviteSender(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.channel_id = get_int_env("INVITE_HUB_CHANNEL_ID")

        self._lock = asyncio.Lock()
        self.message_cache: discord.Message | None = None

        self.next_run_ts = None

        # ตั้ง interval เริ่มต้น
        self.send_invites_task.change_interval(
            seconds=self.get_interval_seconds()
        )

    # ---------- INTERVAL SYSTEM ----------
    def get_interval_seconds(self):
        minutes = get_int_env("INVITE_SYNC_INTERVAL_MINUTES", 30)
        seconds = get_int_env("INVITE_SYNC_INTERVAL_SECONDS", 0)

        total = (minutes * 60) + seconds

        return max(total, 10)  # ป้องกันตั้งต่ำเกิน

    # ---------- INVITE CREATOR ----------
    async def create_invite_for_guild(self, guild: discord.Guild):
        try:
            if guild.unavailable:
                return None

            target = (
                guild.system_channel
                or next(
                    (c for c in guild.text_channels
                     if guild.me and c.permissions_for(guild.me).create_instant_invite),
                    None
                )
            )

            if not target:
                return None

            invite = await target.create_invite(
                max_age=0,
                max_uses=0,
                unique=False,
                reason="InviteHub auto sync"
            )

            return guild.name, invite.url

        except Exception:
            return None

    async def _send_or_edit_chunked_message(
        self,
        channel: discord.abc.Messageable,
        content: str,
        view: discord.ui.View
    ):
        """Prevent Message Too Long when bot is in many guilds."""
        limit = 1900
        chunks = []
        remaining = content

        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break

            cut = remaining.rfind("\n", 0, limit)
            if cut == -1:
                cut = limit

            chunks.append(remaining[:cut])
            remaining = remaining[cut:].lstrip("\n")

        first_chunk = chunks[0] if chunks else content

        if self.message_cache:
            try:
                await self.message_cache.edit(content=first_chunk, view=view)
            except Exception:
                self.message_cache = await channel.send(first_chunk, view=view)
        else:
            self.message_cache = await channel.send(first_chunk, view=view)

        for extra_chunk in chunks[1:]:
            await channel.send(extra_chunk)

    # ---------- MAIN SYNC ----------
    async def run_sync_task(self, manual=False):

        async with self._lock:

            channel = self.bot.get_channel(self.channel_id)
            if not channel:
                return

            invite_infos = []
            copy_list = []

            success = 0
            failed = 0

            sorted_guilds = sorted(self.bot.guilds, key=lambda g: g.name.lower())
            semaphore = asyncio.Semaphore(5)

            async def fetch_invite(guild: discord.Guild):
                async with semaphore:
                    return await self.create_invite_for_guild(guild)

            results = await asyncio.gather(*(fetch_invite(guild) for guild in sorted_guilds))

            for result in results:
                if result:
                    name, link = result
                    invite_infos.append((name, link))
                    copy_list.append(f"{name} -> {link}")
                    success += 1
                else:
                    failed += 1

            ts = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

            # คำนวณรอบถัดไป
            interval = self.get_interval_seconds()
            self.next_run_ts = time.time() + interval

            m = interval // 60
            s = interval % 60
            countdown = f"{m}m {s}s" if m else f"{s}s"

            if not invite_infos:
                body = "⚠️ ไม่มีเซิร์ฟเวอร์ที่สามารถสร้างลิงก์เชิญได้"
            else:
                body = "\n".join(
                    f"**{name}**\n{link}"
                    for name, link in invite_infos
                )

            content = (
                "📨 **AUTO INVITE SYNC**\n"
                f"{body}\n\n"
                f"⏱ Last synced: **{ts}**\n"
                f"⏳ Next run in: **{countdown}**\n\n"
                f"📊 Results: **{success} Success | {failed} Failed**"
            )

            view = InviteRefreshButton(self, "\n".join(copy_list))
            await self._send_or_edit_chunked_message(channel, content, view)

    # ---------- AUTO LOOP ----------
    @tasks.loop(seconds=10)
    async def send_invites_task(self):

        await self.bot.wait_until_ready()

        # ถึงเวลาแล้วค่อยซิงก์
        if self.next_run_ts and time.time() >= self.next_run_ts:

            await self.run_sync_task()

            # โหลด interval ใหม่แบบ runtime
            self.send_invites_task.change_interval(
                seconds=self.get_interval_seconds()
            )

    @send_invites_task.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    # ---------- SLASH : SET INTERVAL ----------
    @app_commands.command(
        name="invite_set_interval",
        description="ตั้งเวลาซิงก์ใหม่ (หน่วยวินาที)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_interval(self, interaction: discord.Interaction, seconds: int):

        if seconds < 10:
            await interaction.response.send_message(
                "⚠️ ขั้นต่ำ 10 วินาที",
                ephemeral=True
            )
            return

        os.environ["INVITE_SYNC_INTERVAL_SECONDS"] = str(seconds)

        self.send_invites_task.change_interval(seconds=seconds)
        self.next_run_ts = time.time() + seconds

        await interaction.response.send_message(
            f"✅ ตั้งเวลาซิงก์ใหม่เป็น **{seconds}s** แล้ว",
            ephemeral=True
        )

    # ---------- START AFTER READY ----------
    @commands.Cog.listener()
    async def on_ready(self):

        if self.channel_id and not self.send_invites_task.is_running():
            self.send_invites_task.start()

        # ⭐ สำคัญ — ให้ส่งครั้งแรกทันที ⭐
        if not self.message_cache:
            await self.run_sync_task(manual=True)


# ---------- REGISTER ----------
async def setup(bot):
    await bot.add_cog(InviteSender(bot))
