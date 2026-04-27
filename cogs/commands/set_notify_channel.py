from discord.ext import commands
from discord import app_commands
import discord
import logging
from utils import async_get_server_config, async_save_server_config

class SetNotifyChannel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="set_notify_channel", description="ตั้งค่าช่องแจ้งเตือนสำหรับกิลนี้")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_notify_channel(self, interaction: discord.Interaction):
        gid, cid = str(interaction.guild.id), interaction.channel.id
        conf = await async_get_server_config(gid) or {}
        if conf.get("notify_channel_id") == cid:
            await interaction.response.send_message("⚠️ ช่องนี้ถูกตั้งค่าเป็นช่องแจ้งเตือนอยู่แล้ว", ephemeral=True)
            return
        conf["notify_channel_id"] = cid
        await async_save_server_config(gid, conf)
        await interaction.response.send_message(f"🔔 ตั้งค่าช่องแจ้งเตือนเป็น: <#{cid}>", ephemeral=True)

    @set_notify_channel.error
    async def _err(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)
        else:
            logging.error(f"❌ เกิดข้อผิดพลาด: {error}")
            await interaction.response.send_message("❌ ตั้งค่าช่องแจ้งเตือนล้มเหลว", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(SetNotifyChannel(bot))
