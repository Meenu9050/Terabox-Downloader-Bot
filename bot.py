#!/usr/bin/env python3
# bot.py - TeraBox Downloader Bot (Mode 2: Bot token)
# Requirements: pyrogram, tgcrypto, aiohttp, python-dotenv, pillow, tqdm
import os
import asyncio
import aiohttp
import time
import pathlib
import tempfile
from aiohttp import ClientTimeout
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID") or None
API_HASH = os.getenv("API_HASH") or None
DOWNLOAD_PATH = os.getenv("DOWNLOAD_PATH", "/tmp")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "5120"))  # default 5GB
CONCURRENT_DOWNLOADS = int(os.getenv("CONCURRENT_DOWNLOADS", "2"))
DOWNLOAD_RETRIES = int(os.getenv("DOWNLOAD_RETRIES", "3"))
LOGGER_GROUP_ID = int(os.getenv("LOGGER_GROUP_ID", "-1002673174815"))  # default from your context
SUPPORT_GROUP = os.getenv("SUPPORT_GROUP", "@HydraxSupport")  # clickable support group name/username
OWNER_ID = int(os.getenv("OWNER_ID")) if os.getenv("OWNER_ID") else None

if not BOT_TOKEN:
    raise SystemExit("Please set BOT_TOKEN in environment or .env file")

app = Client(
    "terabox_bot",
    bot_token=BOT_TOKEN,
    api_id=int(API_ID) if API_ID else None,
    api_hash=API_HASH if API_HASH else None,
)

sema = asyncio.Semaphore(CONCURRENT_DOWNLOADS)

def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Y{suffix}"

def extract_urls(text: str):
    import re
    if not text:
        return []
    # simple URL regex
    urls = re.findall(r'(https?://[^\s]+)', text)
    return urls

async def send_to_logger(text: str):
    try:
        await app.send_message(LOGGER_GROUP_ID, text)
    except Exception as e:
        print("Logger send failed:", e)

async def download_stream(session, url, dest_path, progress_cb=None, max_retries=3):
    headers = {}
    mode = 'wb'
    existing = 0
    if os.path.exists(dest_path):
        existing = os.path.getsize(dest_path)
        if existing > 0:
            headers['Range'] = f'bytes={existing}-'
            mode = 'ab'
    retries = 0
    while retries <= max_retries:
        try:
            timeout = ClientTimeout(total=3600)
            async with session.get(url, headers=headers, timeout=timeout) as resp:
                if resp.status in (200, 206):
                    total = None
                    # try to infer total size
                    if 'Content-Range' in resp.headers:
                        try:
                            total = int(resp.headers['Content-Range'].split('/')[-1])
                        except Exception:
                            total = None
                    else:
                        try:
                            cl = resp.headers.get('Content-Length')
                            total = int(cl) if cl else None
                        except Exception:
                            total = None
                    total_full = (total + existing) if total else None
                    if total_full and MAX_FILE_SIZE_MB and total_full > MAX_FILE_SIZE_MB * 1024 * 1024:
                        raise ValueError(f"File size {sizeof_fmt(total_full)} exceeds max allowed {MAX_FILE_SIZE_MB} MB")
                    downloaded = existing
                    chunk = 1024 * 64
                    start = time.time()
                    with open(dest_path, mode) as f:
                        async for data in resp.content.iter_chunked(chunk):
                            if not data:
                                break
                            f.write(data)
                            downloaded += len(data)
                            if progress_cb:
                                await progress_cb(downloaded, total_full, start)
                    return dest_path, total_full
                else:
                    raise RuntimeError(f"Bad response status: {resp.status}")
        except Exception as e:
            retries += 1
            if retries > max_retries:
                raise
            await asyncio.sleep(2 ** retries)
    raise RuntimeError("Max retries exceeded")

async def upload_and_send(client, chat_id, path, caption=None):
    # Try to send as document. Telegram may reject > bot limits; handle exceptions.
    try:
        await client.send_document(chat_id, document=path, caption=caption)
        return True, None
    except Exception as e:
        return False, str(e)

async def progress_callback_edit(m: Message, cur, total, start_time):
    # Build a small progress text and edit message (once per second)
    try:
        if total:
            percent = cur * 100 / total if total else 0
            elapsed = int(time.time() - start_time)
            speed = cur / max(1, elapsed)
            eta = int((total - cur) / speed) if speed > 0 and total else 0
            txt = (f"⏬ Downloading...\\n{sizeof_fmt(cur)} / {sizeof_fmt(total)} ({percent:.2f}%)\\n"
                   f"Speed: {sizeof_fmt(speed)}/s | Elapsed: {elapsed}s | ETA: {eta}s")
        else:
            txt = f"⏬ Downloading...\\n{sizeof_fmt(cur)} downloaded | Elapsed: {int(time.time()-start_time)}s"
        await m.edit(txt)
    except Exception:
        pass

async def handle_task(message: Message, url: str):
    async with sema:
        user = message.from_user
        uname = f\"@{user.username}\" if user and user.username else (user.first_name if user else \"Unknown\")
        # Log start
        log_text = f\"🟢 New download request\\nUser: {uname} ({user.id if user else 'N/A'})\\nLink: {url}\\nChat: {message.chat.title or message.chat.first_name if message.chat else 'private'}\"\n        await send_to_logger(log_text)
        status = await message.reply_text(\"🔎 Resolving link and preparing to download...\")\n        try:\n            async with aiohttp.ClientSession() as session:\n                # resolve final url and attempt to get filename\n                async with session.get(url, allow_redirects=True, timeout=15) as r:\n                    final = str(r.url)\n                    cd = r.headers.get('Content-Disposition')\n                    if cd and 'filename=' in cd:\n                        fname = cd.split('filename=')[-1].strip(' \\\"')\n                    else:\n                        fname = pathlib.Path(r.url.path).name or 'file'\n                    total = int(r.headers.get('Content-Length') or 0) if r.headers.get('Content-Length') else None\n                # prepare dest\n                safe = pathlib.Path(fname).name\n                dest = os.path.join(DOWNLOAD_PATH, safe)\n                base, ext = os.path.splitext(dest)\n                i = 1\n                while os.path.exists(dest):\n                    dest = f\"{base}_{i}{ext}\"\n                    i += 1\n                # progress cb\n                last = 0\n                async def prog_cb(cur, tot, s_time):\n                    nonlocal last, status\n                    now = time.time()\n                    if now - last >= 1:\n                        await progress_callback_edit(status, cur, tot or 0, s_time)\n                        last = now\n                await status.edit(\"⬇️ Download started...\")\n                await download_stream(session, final, dest, progress_cb=prog_cb, max_retries=DOWNLOAD_RETRIES)\n        except Exception as e:\n            await status.edit(f\"❌ Download failed: {e}\\nSupport: {SUPPORT_GROUP}\")\n            await send_to_logger(f\"❌ Download error for {url}: {e}\")\n            return\n        # upload\n        try:\n            await status.edit(\"⬆️ Uploading to Telegram...\")\n            cap = f\"Downloaded from: {url}\\nRequested by: {uname}\"\n            ok, err = await upload_and_send(app, message.chat.id, dest, caption=cap)\n            if not ok:\n                await status.edit(f\"❌ Upload failed: {err}\\nSupport: {SUPPORT_GROUP}\\nPartial file at: {dest}\")\n                await send_to_logger(f\"❌ Upload failed for {dest}: {err}\")\n                return\n            await status.delete()\n            await send_to_logger(f\"✅ Completed: {safe} for {uname} ({user.id if user else 'N/A'})\")\n        finally:\n            try:\n                if os.path.exists(dest):\n                    os.remove(dest)\n            except Exception:\n                pass\n\n@app.on_message(filters.command('start') & filters.private)\nasync def start_cmd(c: Client, m: Message):\n    user = m.from_user\n    uname = f\"@{user.username}\" if user.username else user.first_name\n    welcome = (\n        f\"👋 Hello {uname}!\\n\\n\"\n        \"Main TeraBox Downloader Bot hoon. Aap mujhe public TeraBox/DuBox link ya direct video link bhej sakte hain, main usko download karke aapko Telegram par bhej dunga.\\n\\n\"\n        \"🔹 Kaise link bheje: Simply paste the TeraBox share link or direct file URL in this chat.\\n\"\n        \"🔹 Agar koi error aaye: Join support group and ask for help: \" + SUPPORT_GROUP + \"\\n\\n\"\n        \"✨ Commands:\\n/start - Show this message\\n/help - How to use\\n/share - Share bot with your friends\\n\\n\"\n        \"🛡️ Note: Files up to 5GB are allowed (subject to Telegram limits). If Telegram rejects large uploads, you will be given a partial file path or direct download link.\\n\\n\"\n        \"👑 Owner & Help: Contact owner via the support group.\\n\\n\"\n        \"✅ Enjoy — and don't forget to share!\"\n    )\n    kb = InlineKeyboardMarkup([\n        [InlineKeyboardButton('Support Group', url=f'https://t.me/{SUPPORT_GROUP.lstrip(\"@\")}')],\n        [InlineKeyboardButton('Share Bot', switch_inline_query='')]\n    ])\n    await m.reply_text(welcome, reply_markup=kb)\n    # log user start\n    await send_to_logger(f\"👤 /start by {uname} ({user.id})\")\n\n@app.on_message(filters.private & filters.text & ~filters.command)\nasync def private_text(c: Client, m: Message):\n    text = m.text or m.caption or ''\n    urls = extract_urls(text)\n    user = m.from_user\n    # log search/usage\n    if text:\n        await send_to_logger(f\"🔎 Message from {user.id} ({user.first_name}): {text[:400]}\")\n    if not urls:\n        await m.reply_text(\"Koi valid link nahi mila. Please send a valid public TeraBox/DuBox share link or direct file URL.\")\n        return\n    # take first URL\n    url = urls[0]\n    await m.reply_text(\"✅ Link received. Starting download shortly...\")\n    asyncio.create_task(handle_task(m, url))\n\n@app.on_message(filters.command('help') & filters.private)\nasync def help_cmd(c: Client, m: Message):\n    txt = (\n        \"How to use:\\n\"\n        \"1. Paste a public TeraBox/DuBox share link or direct file URL in this chat.\\n\"\n        \"2. Bot will download and upload the file back to you.\\n\"\n        \"3. If upload fails (large files), you will be given the server file path for manual download.\\n\\n\"\n        f\"Support: {SUPPORT_GROUP}\\n\"\n    )\n    await m.reply_text(txt)\n\n@app.on_message(filters.command('share') & filters.private)\nasync def share_cmd(c: Client, m: Message):\n    txt = \"Use this bot to download TeraBox links easily. Try it: https://t.me/YourBotUsername\"\n    await m.reply_text(txt)\n\nif __name__ == '__main__':\n    os.makedirs(DOWNLOAD_PATH, exist_ok=True)\n    print('Bot started...')\n    app.run()\n