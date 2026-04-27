import os
import re
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from io import BytesIO
from PIL import Image
import math
import random

MAX_EMOJI_SIZE = 256 * 1024  # 256KB
MAX_DIMENSION = 128

def has_manage_emojis():
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.manage_emojis
    return app_commands.check(predicate)

class EmojiUploader(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def sanitize_emoji_name(self, filename: str) -> str:
        name = os.path.splitext(filename)[0]
        name = name.replace("-", "_")
        name = re.sub(r"[^a-zA-Z0-9_]", "", name)
        return name[:32] if name else "emoji"

    def resize_image(self, image_path: str) -> bytes:
        with Image.open(image_path) as img:
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            fmt = img.format if img.format in ["PNG", "GIF", "JPEG"] else "PNG"
            if fmt == "JPEG":
                quality = 90
                while True:
                    buffer.seek(0)
                    img.save(buffer, format=fmt, quality=quality, optimize=True)
                    if buffer.tell() <= MAX_EMOJI_SIZE or quality <= 20:
                        break
                    quality -= 5
            else:
                img.save(buffer, format=fmt, optimize=True)
            if buffer.tell() > MAX_EMOJI_SIZE:
                # บีบอีกครึ่ง
                w, h = img.size
                img = img.resize((max(16, w // 2), max(16, h // 2)), Image.Resampling.LANCZOS)
                buffer = BytesIO()
                img.save(buffer, format=fmt, optimize=True)
            buffer.seek(0)
            return buffer.read()

    async def upload_emoji_folder(self, guild: discord.Guild):
        folder = "Emoji"
        if not os.path.exists(folder):
            return None

        existing = {e.name for e in guild.emojis}
        uploaded = skipped = failed = 0

        # รองรับ Nitro: ใช้ guild.emoji_limit ถ้ามี (discord.py 2.4 มี)
        try:
            limit = getattr(guild, "emoji_limit", 50)
        except Exception:
            limit = 50

        for fn in os.listdir(folder):
            if not fn.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                continue

            name = self.sanitize_emoji_name(fn)
            if len(name) < 2 or name in existing:
                skipped += 1
                continue

            if len(guild.emojis) + uploaded >= limit:
                break

            path = os.path.join(folder, fn)
            # exponential backoff base
            backoff = 1.5
            tries = 0

            while True:
                try:
                    img_bytes = self.resize_image(path)
                    emoji = await guild.create_custom_emoji(name=name, image=img_bytes)
                    existing.add(name)
                    uploaded += 1
                    await asyncio.sleep(0.8)  # ถี่น้อยลง
                    break
                except discord.HTTPException as e:
                    tries += 1
                    # ถ้า rate limit ให้รอเพิ่มแบบ backoff
                    if e.status == 429:
                        wait = min(30, (backoff ** tries) + random.uniform(0, 1))
                        await asyncio.sleep(wait)
                        continue
                    else:
                        failed += 1
                        break
                except discord.Forbidden:
                    return False
                except Exception:
                    failed += 1
                    break

        return uploaded, skipped, failed

    @app_commands.command(
        name="upload_emojis_gawrgura",
        description="อัพโหลดอีโมจิจากโฟลเดอร์ Emoji ไปยังเซิร์ฟเวอร์นี้"
    )
    @has_manage_emojis()
    async def upload_emojis_gawrgura(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        result = await self.upload_emoji_folder(interaction.guild)

        if result is None:
            await interaction.followup.send("❌ ไม่พบโฟลเดอร์ Emoji")
            return
        if result is False:
            await interaction.followup.send("❌ บอทไม่มีสิทธิ์อัปโหลดอีโมจิในเซิร์ฟเวอร์นี้")
            return

        uploaded, skipped, failed = result
        msg = f"✅ อัพโหลดใหม่: {uploaded}\n⏭️ ข้าม: {skipped}\n"
        if failed:
            msg += f"❌ ล้มเหลว: {failed}\n"
        await interaction.followup.send(msg)

async def setup(bot):
    await bot.add_cog(EmojiUploader(bot))
