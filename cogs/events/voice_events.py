import logging
from datetime import datetime

import discord
from discord.ext import commands
import pytz

from utils import async_get_server_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
):
    if member.bot:
        return

    cfg = await async_get_server_config(member.guild.id)
    notify_channel_id = cfg.get("notify_channel_id")
    if not notify_channel_id:
        return

    channel = member.guild.get_channel(notify_channel_id)
    if not channel:
        return

    me = member.guild.me
    if not me or not channel.permissions_for(me).send_messages:
        return

    join_here_name = (cfg.get("join_here_channel_name") or "").strip() or None
    thai_time = datetime.now(pytz.timezone("Asia/Bangkok"))

    def _voice_embed(
        event: str,
        *,
        before_channel: discord.VoiceChannel | None = None,
        after_channel: discord.VoiceChannel | None = None,
    ) -> discord.Embed:
        styles = {
            "join": {
                "title": "🟢 แจ้งเตือนเข้า Voice",
                "color": discord.Color.green(),
                "headline": f"{member.mention} เข้าห้องเสียงแล้ว",
            },
            "leave": {
                "title": "🔴 แจ้งเตือนออก Voice",
                "color": discord.Color.red(),
                "headline": f"{member.mention} ออกจากห้องเสียงแล้ว",
            },
            "move": {
                "title": "🟠 แจ้งเตือนย้ายห้อง Voice",
                "color": discord.Color.orange(),
                "headline": f"{member.mention} ย้ายห้องเสียง",
            },
        }

        style = styles[event]
        embed = discord.Embed(
            title=style["title"],
            description=style["headline"],
            color=style["color"],
            timestamp=thai_time,
        )

        embed.set_author(name=f"{member.display_name}", icon_url=member.display_avatar.url)
        embed.add_field(name="👤 ผู้ใช้", value=f"{member.mention} (`{member.id}`)", inline=False)

        if event == "join":
            embed.add_field(
                name="📥 เข้าห้อง",
                value=after_channel.mention if after_channel else "-",
                inline=True,
            )
        elif event == "leave":
            embed.add_field(
                name="📤 ออกจากห้อง",
                value=before_channel.mention if before_channel else "-",
                inline=True,
            )
        else:
            embed.add_field(
                name="↩️ จากห้อง",
                value=before_channel.mention if before_channel else "-",
                inline=True,
            )
            embed.add_field(
                name="➡️ ไปห้อง",
                value=after_channel.mention if after_channel else "-",
                inline=True,
            )

        embed.set_footer(text="BotAll Voice Log • เวลาไทย")
        return embed

    try:
        # join
        if before.channel is None and after.channel is not None:
            if join_here_name and after.channel.name == join_here_name:
                return
            await channel.send(embed=_voice_embed("join", after_channel=after.channel))

        # leave
        elif before.channel is not None and after.channel is None:
            await channel.send(embed=_voice_embed("leave", before_channel=before.channel))

        # move
        elif before.channel != after.channel:
            if join_here_name and before.channel and before.channel.name == join_here_name:
                return

            await channel.send(
                embed=_voice_embed(
                    "move",
                    before_channel=before.channel,
                    after_channel=after.channel,
                )
            )

    except discord.HTTPException as exc:
        logging.error(f"❌ เกิดข้อผิดพลาดขณะส่งข้อความ Voice Notify: {exc}")


async def setup(bot: commands.Bot):
    bot.add_listener(on_voice_state_update, "on_voice_state_update")
