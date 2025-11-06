# TeraBox Downloader Bot (Ready-to-use)

This ZIP contains a ready-to-use Telegram bot (Mode 2: Bot token) that downloads public TeraBox/DuBox links or direct file URLs and uploads them back to users.

Instructions:
1. Copy files to your VPS or unzip locally.
2. Rename `.env.example` to `.env` and fill `BOT_TOKEN`, `LOGGER_GROUP_ID`, and `SUPPORT_GROUP`.
3. Install requirements: `pip install -r requirements.txt`.
4. Run: `python bot.py`.

Notes:
- Default max file size set to 5GB (5120 MB). If Telegram rejects uploads, the bot will provide partial file path.
- The bot logs activity to `LOGGER_GROUP_ID` (change in .env).
