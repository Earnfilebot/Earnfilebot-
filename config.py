import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# 🔥 VALIDASI WAJIB (biar error ketahuan dari awal)
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN belum di-set di .env")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL belum di-set di .env")


CHANNEL_ID = -1003721009353  # group post


# =========================
# PRICE NORMALIZER
# =========================
def normalize_price(text: str):
    return int("".join(filter(str.isdigit, text)))
