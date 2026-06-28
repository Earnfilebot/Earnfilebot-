import os

from dotenv import load_dotenv

load_dotenv()
TIMEZONE = "Asia/Jakarta"
# =========================
# BOT
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "DecoderFileBot"
# =========================
# DATABASE
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")

# =========================
# CHANNEL / GROUP
# =========================
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1004395938795"))
GROUP_ID = int(os.getenv("GROUP_ID", str(CHANNEL_ID)))

# =========================
# VALIDATION
# =========================
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN belum di-set di .env")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL belum di-set di .env")
