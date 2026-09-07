import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "database.db"
)

TIMEZONE = os.getenv(
    "TIMEZONE",
    "Europe/Minsk"
)

ADMIN_TELEGRAM_ID = int(
    os.getenv("ADMIN_TELEGRAM_ID", "0")
)

FOOTBALL_DATA_API_TOKEN = os.getenv("FOOTBALL_DATA_API_TOKEN")

if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN не найден в файле .env"
    )