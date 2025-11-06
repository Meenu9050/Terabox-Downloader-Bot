import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
LOGGER_ID = int(os.getenv("LOGGER_ID", "0"))
SUPPORT_GROUP = os.getenv("SUPPORT_GROUP", "")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "5000")) * 1024 * 1024
