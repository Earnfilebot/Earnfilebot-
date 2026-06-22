import hmac
import hashlib
import json
import logging
import asyncio
from datetime import datetime

from fastapi import APIRouter, Request, Header
from aiogram.types import Update

from database import get_pool
from config import GROUP_ID

router = APIRouter()

logging.basicConfig(level=logging.INFO)

BAYARGG_SECRET = "ISI_SECRET_KAMU"

PROCESSED = set()


# =========================
# SECURITY
# =========================
def verify_signature(body: bytes, signature: str):
    if not signature:
        logging.warning("⚠️ NO SIGNATURE HEADER")
        return False

    expected = hmac.new(
        BAYARGG_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    ok = hmac.compare_digest(expected, signature)

    logging.info(f"🔐 SIGN CHECK: {ok}")

    return ok


def is_paid(status: str):
    return status and status.upper() in ["PAID", "SUCCESS", "SETTLED"]


# =========================
# SAFE SEND
# =========================
async def safe_send(bot, user_id, item):
    try:
        fid = item.get("file_id")
        t = item.get("type")

        if not fid:
            return False

        if t == "video":
            await bot.send_video(user_id, fid)
        elif t == "document":
            await bot.send_document(user_id, fid)
        else:
            await bot.send_photo(user_id, fid)

        return True
    except Exception as e:
        logging.error(f"❌ SEND ERROR: {e}")
        return False


# =========================
# WEBHOOK
# =========================
@router.post("/webhook")
async def webhook(req: Request, x_signature: str = Header(None, alias="X-Signature")):

    logging.info("🔥 WEBHOOK HIT")

    bot = req.app.state.bot
    dp = req.app.state.dp

    body = await req.body()

    # =========================
    # JSON PARSE SAFE
    # =========================
    try:
        data = json.loads(body.decode())
    except Exception as e:
        logging.error(f"❌ INVALID JSON: {e}")
        return {"ok": True}

    # =========================
    # TELEGRAM MODE
    # =========================
    if "update_id" in data and not x_signature:
        try:
            update = Update.model_validate(data)
            await dp.feed_update(bot, update)
            logging.info("✅ TELEGRAM OK")
        except Exception as e:
            logging.exception(e)
        return {"ok": True}

    # =========================
    # BAYARGG MODE
    # =========================
    logging.info("💰 BAYARGG WEBHOOK TRIGGERED")

    logging.info(f"📦 RAW DATA: {data}")

    if not verify_signature(body, x_signature):
        logging.warning("❌ INVALID SIGNATURE")
        return {"ok": True}

    payload = data.get("data") or data

    status = payload.get("status") or data.get("status")
    ref = payload.get("external_id") or data.get("invoice_id")

    logging.info(f"📦 STATUS: {status}")
    logging.info(f"📦 REF: {ref}")

    if not is_paid(status):
        logging.info("⏳ NOT PAID")
        return {"ok": True}

    if ref in PROCESSED:
        logging.warning("⚠️ DUPLICATE BLOCKED")
        return {"ok": True}

    PROCESSED.add(ref)

    pool = await get_pool()

    # =========================
    # FIND PAYMENT
    # =========================
    payment = await pool.fetchrow("""
        SELECT user_id, code
        FROM payments
        WHERE invoice_id=$1 OR external_id=$1 OR code=$1
    """, ref)

    if not payment:
        logging.warning("❌ PAYMENT NOT FOUND")
        return {"ok": True}

    user_id = payment["user_id"]
    code = payment["code"]

    # =========================
    # UPDATE PAYMENT
    # =========================
    await pool.execute("""
        UPDATE payments
        SET status='paid'
        WHERE user_id=$1 AND code=$2
    """, user_id, code)

    # =========================
    # ACCESS
    # =========================
    await pool.execute("""
        INSERT INTO user_access(user_id, code, paid)
        VALUES ($1,$2,TRUE)
        ON CONFLICT (user_id, code)
        DO UPDATE SET paid=TRUE
    """, user_id, code)

    # =========================
    # FILE FETCH
    # =========================
    file = await pool.fetchrow("""
        SELECT seller_id, price, media_json
        FROM files
        WHERE code=$1
    """, code)

    if not file:
        return {"ok": True}

    seller_id = file["seller_id"]
    price = int(file["price"] or 0)

    try:
        media = json.loads(file["media_json"]) if file["media_json"] else []
    except:
        media = []

    # =========================
    # NOTIFY
    # =========================
    await bot.send_message(user_id, f"✅ PAYMENT SUCCESS\nCODE: {code}")

    for item in media:
        await safe_send(bot, user_id, item)
        await asyncio.sleep(0.2)

    logging.info("⚡ DONE")

    return {"ok": True}
