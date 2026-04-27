import logging
import asyncio
from datetime import datetime

import discord
from discord.ext import commands
import pytz

from utils import async_get_server_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

async def on_voice_state_update(member: discord.Member,
                                before: discord.VoiceState,
                                after: discord.VoiceState):
    if member.bot:
        return

    cfg = await async_get_server_config(member.guild.id)
    notify_channel_id = cfg.get("notify_channel_id")
    if not notify_channel_id:
        return

    channel = member.guild.get_channel(notify_channel_id)
    if not channel or not channel.permissions_for(member.guild.me).send_messages:
        return

    join_here_name = (cfg.get("join_here_channel_name") or "").strip() or None

    def embed_for(event: str, *, before_ch: str | None = None, after_ch: str | None = None):
        thai_time = datetime.now(pytz.timezone("Asia/Bangkok"))
        styles = {
            "join":  ("🔊 สมาชิกเข้าช่องเสียง", f"✅ **{member.display_name}** เข้าช่อง **{after_ch}**", discord.Color.green()),
            "leave": ("🔇 สมาชิกออกจากช่องเสียง", f"❌ **{member.display_name}** ออกจากช่อง **{before_ch}**", discord.Color.red()),
            "move":  ("🔀 สมาชิกย้ายช่องเสียง", f"🔄 **{member.display_name}** ย้ายจาก **{before_ch}** ไป **{after_ch}**", discord.Color.orange()),
        }
        title, desc, color = styles[event]
        e = discord.Embed(title=title, description=desc, timestamp=thai_time, color=color)
        e.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        e.set_footer(text="🕒 เวลาที่เกิดเหตุการณ์")
        return e

    try:
        # join
        if before.channel is None and after.channel is not None:
            if join_here_name and after.channel.name == join_here_name:
                return
            await channel.send(embed=embed_for("join", after_ch=after.channel.name))
        # leave
        elif before.channel is not None and after.channel is None:
            await channel.send(embed=embed_for("leave", before_ch=before.channel.name))
        # move
        elif before.channel != after.channel:
            if join_here_name and before.channel and before.channel.name == join_here_name:
                return
            await channel.send(
                embed=embed_for(
                    "move",
                    before_ch=before.channel.name if before.channel else "N/A",
                    after_ch=after.channel.name if after.channel else "N/A",
                )
            )
    except discord.HTTPException as e:
        logging.error(f"❌ เกิดข้อผิดพลาดขณะส่งข้อความ: {e}")

async def setup(bot: commands.Bot):
    bot.add_listener(on_voice_state_update, "on_voice_state_update")
