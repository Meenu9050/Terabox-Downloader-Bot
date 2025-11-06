from pyrogram import Client, filters
from config import BOT_TOKEN, API_ID, API_HASH, OWNER_ID, LOGGER_ID, SUPPORT_GROUP
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

bot = Client(
    "TeraBox-Downloader-Bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@bot.on_message(filters.command("start"))
async def start_command(_, message):
    text = (
        f"👋 Hello {message.from_user.mention}!\n\n"
        "🎥 Send me any **TeraBox link**, and I’ll fetch & send you the video (up to 5GB) for free — no ads or premium needed!\n\n"
        f"If any issue comes, contact support 👉 [Support Group]({SUPPORT_GROUP})\n\n"
        "💡 **Commands:**\n"
        "/start - Show this message\n"
        "/help - How to use\n\n"
        "⚡ Made with ❤️ by Owner"
    )
    await message.reply_text(text, disable_web_page_preview=True)

@bot.on_message(filters.text & ~filters.command(["start", "help"]))
async def handle_link(_, message):
    link = message.text.strip()
    if "terabox.com" not in link:
        return await message.reply("❌ Please send a valid TeraBox link.")
    await message.reply("📥 Downloading your video... please wait!")

    # Placeholder download process (you’ll connect actual TeraBox download logic later)
    await asyncio.sleep(5)
    await message.reply("✅ Done! (Mock download successful)\n\nThis is where real video will appear.")

if __name__ == "__main__":
    LOG.info("Bot starting...")
    bot.run()
