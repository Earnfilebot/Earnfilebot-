import hmac
import hashlib
import json
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Request, Header
from aiogram.types import Update

from database import get_pool
from config import GROUP_ID

router = APIRouter()

BAYARGG_SECRET = str(__import__("os").getenv("BAYARGG_WEBHOOK_SECRET", ""))

# anti duplicate in-memory (production bisa upgrade Redis)
PROCESSED = set()


# =========================
# SECURITY SIGNATURE
# =========================
def verify_signature(raw_body: bytes, signature: str):
    if not signature or not BAYARGG_SECRET:
        logging.warning("⚠️ SIGNATURE OR SECRET EMPTY")
        return False

    expected = hmac.new(
        BAYARGG_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# =========================
# STATUS CHECK
# =========================
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
        logging.error(f"❌ SEND FAIL: {repr(e)}")
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
    # PARSE JSON SAFE
    # =========================
    try:
        data = json.loads(body.decode())
    except Exception as e:
        logging.error(f"❌ INVALID JSON: {e}")
        return {"ok": True}

    # =========================
    # TELEGRAM UPDATE MODE
    # =========================
    if "update_id" in data and not x_signature:
        try:
            update = Update.model_validate(data)
            await dp.feed_update(bot, update)
            logging.info("✅ TELEGRAM PROCESSED")
        except Exception as e:
            logging.exception(f"❌ TELEGRAM ERROR: {e}")

        return {"ok": True}

    # =========================
    # BAYARGG MODE
    # =========================
    logging.info("💰 BAYARGG WEBHOOK")

    # signature check (strict)
    if not verify_signature(body, x_signature):
        logging.warning("❌ INVALID SIGNATURE")
        return {"ok": True}

    payload = data.get("data") or data

    status = (
        payload.get("status")
        or data.get("status")
        or ("PAID" if data.get("success") else None)
    )

    ref = (
        payload.get("external_id")
        or payload.get("reference")
        or data.get("invoice_id")
    )

    logging.info(f"📦 STATUS: {status}")
    logging.info(f"📦 REF: {ref}")

    if not is_paid(status):
        logging.info("⏳ NOT PAID STATUS")
        return {"ok": True}

    # =========================
    # ANTI DUPLICATE (MEMORY)
    # =========================
    if ref in PROCESSED:
        logging.warning("⚠️ DUPLICATE IGNORED")
        return {"ok": True}

    PROCESSED.add(ref)

    pool = await get_pool()

    # =========================
    # FIND PAYMENT (ROBUST MATCH)
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

    try:
        # =========================
        # UPDATE PAYMENT (IDEMPOTENT)
        # =========================
        await pool.execute("""
            UPDATE payments
            SET status='paid'
            WHERE user_id=$1 AND code=$2
        """, user_id, code)

        # =========================
        # GRANT ACCESS
        # =========================
        await pool.execute("""
            INSERT INTO user_access(user_id, code, paid)
            VALUES ($1,$2,TRUE)
            ON CONFLICT (user_id, code)
            DO UPDATE SET paid=TRUE
        """, user_id, code)

        # =========================
        # GET FILE
        # =========================
        file = await pool.fetchrow("""
            SELECT seller_id, price, media_json
            FROM files
            WHERE code=$1
        """, code)

        if not file:
            logging.warning("❌ FILE NOT FOUND")
            return {"ok": True}

        seller_id = file["seller_id"]
        price = int(file["price"] or 0)

        try:
            media = json.loads(file["media_json"]) if file["media_json"] else []
        except:
            media = []

        fee = int(price * 0.10)
        seller_income = price - fee

        await pool.execute("""
            INSERT INTO users (telegram_id, balance)
            VALUES ($1,$2)
            ON CONFLICT (telegram_id)
            DO UPDATE SET balance = users.balance + EXCLUDED.balance
        """, seller_id, seller_income)

        # =========================
        # NOTIFY USER
        # =========================
        await bot.send_message(
            user_id,
            f"✅ PAYMENT SUCCESS\nCODE: {code}\nFILES: {len(media)}"
        )

        # =========================
        # SEND FILES
        # =========================
        for item in media:
            await safe_send(bot, user_id, item)
            await asyncio.sleep(0.2)

        # =========================
        # GROUP LOG
        # =========================
        if GROUP_ID:
            await bot.send_message(
                int(GROUP_ID),
                f"💰 PAYMENT SUCCESS\nCODE: {code}\nUSER: {user_id}\nPRICE: Rp {price}"
            )

        logging.info("⚡ PAYMENT COMPLETED")

    except Exception as e:
        logging.exception(f"❌ WEBHOOK ERROR: {e}")

    return {"ok": True}
