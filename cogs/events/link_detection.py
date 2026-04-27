import re
import asyncio
import time
import discord
from discord.ext import commands
from discord import app_commands

from utils import (
    async_get_server_config,
    async_save_server_config
)


SAFE_TLDS = (
    "com", "net", "org", "app", "io", "me",
    "co", "tv", "gg", "edu", "gov"
)


class LinkFilter(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config_ttl_sec = 15
        self.config_cache: dict[str, tuple[float, dict]] = {}

        # ตรวจจับเฉพาะลิงก์จริง (ลด false positive)
        self.link_pattern = re.compile(
            r"(?i)\b((https?|ftp):\/\/)?"
            r"([a-z0-9.-]+\.[a-z]{2,15})"
            r"([\/?#][^\s]*)?"
        )

        # กันบอททำงานซ้ำบนข้อความเดียว
        self.processing = set()


    # ---------- CONFIG HELPERS ----------
    async def load_config(self, guild_id: str):
        now = time.time()
        cached = self.config_cache.get(guild_id)
        if cached and (now - cached[0]) < self.config_ttl_sec:
            return cached[1]

        # Keep full config object to avoid dropping unrelated keys
        # (e.g. join_here_channel_name) when saving updates.
        cfg = await async_get_server_config(guild_id) or {}
        cfg.setdefault("notify_channel_id", None)
        cfg["exempt_channels"] = set(cfg.get("exempt_channels", []))
        cfg["exempt_guild"] = bool(cfg.get("exempt_guild", False))
        self.config_cache[guild_id] = (now, cfg)
        return cfg

    async def save_config(self, guild_id: str, cfg, **updates):
        cfg.update(updates)
        await async_save_server_config(guild_id, cfg)
        self.config_cache[guild_id] = (time.time(), cfg)


    # ---------- ADMIN CONTROLS ----------
    @app_commands.command(
        name="add_exempt_channel",
        description="เพิ่มห้องที่ไม่ต้องตรวจลิงก์"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def add_exempt_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        gid = str(interaction.guild.id)
        cfg = await self.load_config(gid)

        if channel.id in cfg["exempt_channels"]:
            await interaction.response.send_message("⚠️ ห้องนี้ถูกยกเว้นอยู่แล้ว", ephemeral=True)
            return

        cfg["exempt_channels"].add(channel.id)

        await self.save_config(gid, cfg,
            exempt_channels=list(cfg["exempt_channels"])
        )

        await interaction.response.send_message(
            f"✅ เพิ่ม {channel.mention} เข้ารายการยกเว้น",
            ephemeral=True
        )


    @app_commands.command(
        name="remove_exempt_channel",
        description="เอาห้องออกจากรายการยกเว้น"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_exempt_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        gid = str(interaction.guild.id)
        cfg = await self.load_config(gid)

        if channel.id not in cfg["exempt_channels"]:
            await interaction.response.send_message("⚠️ ห้องนี้ไม่ได้อยู่ในรายการ", ephemeral=True)
            return

        cfg["exempt_channels"].remove(channel.id)

        await self.save_config(gid, cfg,
            exempt_channels=list(cfg["exempt_channels"])
        )

        await interaction.response.send_message(
            f"❌ เอา {channel.mention} ออกจากรายการแล้ว",
            ephemeral=True
        )


    @app_commands.command(
        name="exempt_all_channels",
        description="ยกเว้นทั้งเซิร์ฟเวอร์จากระบบกรองลิงก์"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def exempt_all(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        cfg = await self.load_config(gid)

        if cfg["exempt_guild"]:
            await interaction.response.send_message("⚠️ ทั้งเซิร์ฟเวอร์ถูกยกเว้นอยู่แล้ว", ephemeral=True)
            return

        await self.save_config(gid, cfg, exempt_guild=True)

        await interaction.response.send_message(
            "✅ ยกเว้นทั้งเซิร์ฟเวอร์แล้ว",
            ephemeral=True
        )


    @app_commands.command(
        name="unexempt_all_channels",
        description="ยกเลิกการยกเว้นทั้งเซิร์ฟเวอร์"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def unexempt_all(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        cfg = await self.load_config(gid)

        if not cfg["exempt_guild"]:
            await interaction.response.send_message("⚠️ ยังไม่ได้ถูกยกเว้น", ephemeral=True)
            return

        await self.save_config(gid, cfg, exempt_guild=False)

        await interaction.response.send_message(
            "❌ ยกเลิกการยกเว้นแล้ว",
            ephemeral=True
        )


    # ---------- MESSAGE FILTER ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        # DM / System / Bot → ข้าม
        if not message.guild:
            return

        if message.author.bot:
            return

        if message.type != discord.MessageType.default:
            return

        gid = str(message.guild.id)
        cfg = await self.load_config(gid)

        # ทั้งกิลด์ถูกยกเว้น
        if cfg["exempt_guild"]:
            return

        # ห้องถูกยกเว้น
        if message.channel.id in cfg["exempt_channels"]:
            return

        text = (message.content or "").strip()

        matches = self.link_pattern.findall(text)

        if not matches:
            return

        # สกัดเฉพาะโดเมนจริง
        safe_suffixes = tuple(f".{tld}" for tld in SAFE_TLDS)
        domains = {
            m[2].lower()
            for m in matches
            if m[2].lower().endswith(safe_suffixes)
        }

        if not domains:
            return

        # กันทำซ้ำข้อความเดิม
        if message.id in self.processing:
            return

        self.processing.add(message.id)

        try:
            original_text = message.content

            # ลบข้อความต้นฉบับ
            try:
                await message.delete()
            except Exception:
                pass

            # ส่งคืนข้อความเดิม + แสดงชื่อคนส่ง
            # (ให้ลิงก์ preview ได้ตามปกติ)
            await message.channel.send(
                f"👤 **{message.author.display_name}**\n{original_text}"
            )

        finally:
            self.processing.discard(message.id)


async def setup(bot):
    await bot.add_cog(LinkFilter(bot))
