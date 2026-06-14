import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
BAYARGG_API_KEY = os.getenv("BAYARGG_API_KEY")

# 🔥 FIX ENDPOINT
BAYARGG_BASE_URL = "https://api.bayar.gg/api"

# =========================
# VALIDASI
# =========================
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN belum di-set di .env")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL belum di-set di .env")

if not BAYARGG_API_KEY:
    raise ValueError("BAYARGG_API_KEY belum di-set di .env")


CHANNEL_ID = -1003721009353


# =========================
# PRICE NORMALIZER
# =========================
def normalize_price(text: str):
    return int("".join(filter(str.isdigit, text)))
