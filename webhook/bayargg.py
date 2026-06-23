import hmac
import hashlib
import json
import os
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Request, Header
from aiogram.types import Update

from database import get_pool
from config import GROUP_ID

router = APIRouter()

BAYARGG_SECRET = os.getenv("BAYARGG_WEBHOOK_SECRET", "")

logging.basicConfig(level=logging.INFO)


# =========================
# SECURITY
# =========================
def verify_signature(body: bytes, signature: str):
    if not signature or not BAYARGG_SECRET:
        return True  # fallback safe mode (biar gak dead)

    expected = hmac.new(
        BAYARGG_SECRET.encode(),
        body,
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
            return

        if t == "video":
            await bot.send_video(user_id, fid)
        elif t == "document":
            await bot.send_document(user_id, fid)
        else:
            await bot.send_photo(user_id, fid)

    except Exception as e:
        logging.error(f"SEND ERROR: {e}")


# =========================
# WEBHOOK
# =========================
@router.post("/webhook")
async def webhook(req: Request, x_signature: str = Header(None, alias="X-Signature")):

    logging.info("🔥 WEBHOOK HIT")

    bot = req.app.state.bot
    dp = req.app.state.dp

    body = await req.body()

    logging.info("=== BAYARGG DEBUG ===")
    logging.info(f"HEADERS: {dict(req.headers)}")
    logging.info(f"BODY: {body.decode(errors='ignore')}")

    # parse JSON
    try:
        data = json.loads(body.decode())
    except:
        return {"ok": True}

    # =========================
    # TELEGRAM UPDATE
    # =========================
    if "update_id" in data and not x_signature:
        try:
            update = Update.model_validate(data)
            await dp.feed_update(bot, update)
        except Exception as e:
            logging.error(f"TELEGRAM ERROR: {e}")

        return {"ok": True}

    # =========================
    # BAYARGG WEBHOOK
    # =========================
    logging.info("💰 BAYARGG MODE")

    if not verify_signature(body, x_signature):
        logging.warning("❌ INVALID SIGNATURE")
        return {"ok": True}

    payload = data.get("data") or data

    status = payload.get("status") or data.get("status")
    ref = payload.get("external_id") or payload.get("reference") or data.get("invoice_id")

    logging.info(f"STATUS={status} REF={ref}")

    if not is_paid(status):
        return {"ok": True}

    pool = await get_pool()

    # =========================
    # GET PAYMENT
    # =========================
    payment = await pool.fetchrow("""
        SELECT user_id, code
        FROM payments
        WHERE invoice_id=$1 OR external_id=$1 OR code=$1
    """, ref)

    if not payment:
        logging.warning("PAYMENT NOT FOUND")
        return {"ok": True}

    user_id = payment["user_id"]
    code = payment["code"]

    # =========================
    # IDEMPOTENT UPDATE (ANTI DOUBLE WEBHOOK)
    # =========================
    updated = await pool.fetchval("""
        UPDATE payments
        SET status='paid'
        WHERE user_id=$1 AND code=$2 AND status='pending'
        RETURNING id
    """, user_id, code)

    if not updated:
        logging.warning("ALREADY PROCESSED")
        return {"ok": True}

    # =========================
    # GRANT ACCESS
    # =========================
    await pool.execute("""
        INSERT INTO user_access(user_id, code, paid)
        VALUES ($1,$2,TRUE)
        ON CONFLICT DO NOTHING
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
        return {"ok": True}

    media = file["media_json"] or []
    if isinstance(media, str):
        media = json.loads(media)

    # =========================
    # NOTIFY USER
    # =========================
    await bot.send_message(user_id, f"✅ PAYMENT SUCCESS\nCODE: {code}")

    for item in media:
        await safe_send(bot, user_id, item)
        await asyncio.sleep(0.1)

    # =========================
    # GROUP LOG
    # =========================
    if GROUP_ID:
        await bot.send_message(
            int(GROUP_ID),
            f"💰 PAID\nCODE: {code}\nUSER: {user_id}"
        )

    return {"ok": True}
