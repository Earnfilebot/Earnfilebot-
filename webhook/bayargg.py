import hmac
import hashlib
import json
import os
import logging
import asyncio
from datetime import datetime

from fastapi import APIRouter, Request, Header
from aiogram.types import Update

from database import get_pool
from config import GROUP_ID

router = APIRouter()
logging.basicConfig(level=logging.INFO)

BAYARGG_SECRET = os.getenv("BAYARGG_WEBHOOK_SECRET", "")


# =========================
# UTILS
# =========================
def parse_reference(ref: str):
    try:
        user_id, code = ref.split("_", 1)
        return int(user_id), code
    except:
        return None, None


def verify_signature(body: bytes, signature: str):
    if not signature:
        return False

    if not BAYARGG_SECRET:
        logging.error("❌ SECRET NOT SET")
        return False

    expected = hmac.new(
        BAYARGG_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def is_paid_status(status: str):
    return status and status.upper() in ["PAID", "SUCCESS", "SETTLED"]


# =========================
# TELEGRAM WEBHOOK
# =========================
@router.post("/webhook/telegram")
async def telegram_webhook(req: Request):
    logging.info("🤖 TELEGRAM HIT")

    bot = req.app.state.bot
    dp = req.app.state.dp

    body = await req.json()

    try:
        update = Update.model_validate(body)
        await dp.feed_update(bot, update)
    except Exception as e:
        logging.exception(f"❌ TELEGRAM ERROR: {e}")

    return {"ok": True}


# =========================
# BAYARGG WEBHOOK
# =========================
@router.post("/webhook/bayargg")
async def bayargg_webhook(
    req: Request,
    x_signature: str = Header(None, alias="X-Signature")
):
    start_time = datetime.utcnow()
    logging.info("💰 BAYARGG HIT")

    bot = req.app.state.bot

    body = await req.body()

    # DEBUG (penting banget kalau ada error)
    logging.info(f"BODY: {body.decode()}")

    try:
        data = json.loads(body.decode())
    except Exception as e:
        logging.error(f"❌ INVALID JSON: {e}")
        return {"ok": True}

    # =========================
    # VERIFY SIGNATURE
    # =========================
    if not verify_signature(body, x_signature):
        logging.warning("❌ INVALID SIGNATURE")
        return {"ok": True}

    payload = data.get("data") or data

    status = payload.get("status")
    ref = payload.get("reference")

    logging.info(f"STATUS={status} REF={ref}")

    if not is_paid_status(status):
        logging.info("⛔ NOT PAID")
        return {"ok": True}

    user_id, code = parse_reference(ref)

    if not user_id or not code:
        logging.warning("❌ INVALID REF")
        return {"ok": True}

    pool = await get_pool()

    try:
        # =========================
        # ANTI DUPLICATE
        # =========================
        payment_id = await pool.fetchval("""
            UPDATE payments
            SET status='paid'
            WHERE user_id=$1 AND code=$2 AND status='pending'
            RETURNING id
        """, user_id, code)

        if not payment_id:
            logging.warning("❌ ALREADY PROCESSED")
            return {"ok": True}

        file = await pool.fetchrow("""
            SELECT seller_id, price, media_json
            FROM files
            WHERE code=$1
        """, code)

        if not file:
            logging.warning("❌ FILE NOT FOUND")
            return {"ok": True}

        seller_id = file["seller_id"]
        price = int(file["price"])
        media_json = file["media_json"]

        fee = int(price * 0.10)
        seller_income = price - fee

        # =========================
        # UPDATE BALANCE
        # =========================
        await pool.execute("""
            INSERT INTO users (telegram_id, balance)
            VALUES ($1, $2)
            ON CONFLICT (telegram_id)
            DO UPDATE SET balance = users.balance + EXCLUDED.balance
        """, seller_id, seller_income)

        # =========================
        # SEND FILE
        # =========================
        try:
            media_list = json.loads(media_json) if isinstance(media_json, str) else (media_json or [])

            await bot.send_message(
                user_id,
                f"""✅ PEMBAYARAN BERHASIL

📦 {code}
📁 {len(media_list)} file
━━━━━━━━━━━━━━"""
            )

            for item in media_list:
                t = item.get("type")
                fid = item.get("file_id")

                if t == "document":
                    await bot.send_document(user_id, fid)
                elif t == "video":
                    await bot.send_video(user_id, fid)
                elif t == "photo":
                    await bot.send_photo(user_id, fid)

                await asyncio.sleep(0.3)

        except Exception as e:
            logging.error(f"❌ SEND ERROR: {e}")

        # =========================
        # GROUP LOG
        # =========================
        if GROUP_ID:
            await bot.send_message(
                int(GROUP_ID),
                f"💰 {code} | Rp {price:,} | {user_id}"
            )

    except Exception as e:
        logging.exception(f"❌ DB ERROR: {e}")

    duration = (datetime.utcnow() - start_time).total_seconds()
    logging.info(f"⚡ DONE {duration:.2f}s")

    return {"ok": True}
