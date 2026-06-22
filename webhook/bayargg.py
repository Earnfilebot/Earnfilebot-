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

# =========================
# CONFIG
# =========================
import os
BAYARGG_SECRET = os.getenv("BAYARGG_WEBHOOK_SECRET", "")

logging.basicConfig(level=logging.INFO)


# =========================
# SECURITY
# =========================
def verify_signature(body: bytes, signature: str) -> bool:
    if not signature or not BAYARGG_SECRET:
        return False

    expected = hmac.new(
        BAYARGG_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# =========================
# STATUS CHECK
# =========================
def is_paid(status: str) -> bool:
    return status and status.upper() in ["PAID", "SUCCESS", "SETTLED"]


# =========================
# SAFE SEND FILE
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

    start = datetime.utcnow()
    logging.info("🔥 WEBHOOK HIT")

    bot = req.app.state.bot
    dp = req.app.state.dp

    body = await req.body()

    try:
        data = json.loads(body.decode())
    except Exception as e:
        logging.error(f"❌ INVALID JSON: {e}")
        return {"ok": True}

    logging.info(f"📦 RAW: {data}")


    # =========================
    # TELEGRAM UPDATE
    # =========================
    if "update_id" in data:
        logging.info("📩 TELEGRAM UPDATE")

        try:
            update = Update.model_validate(data)
            await dp.feed_update(bot, update)
        except Exception as e:
            logging.error(f"❌ TELEGRAM ERROR: {e}")

        return {"ok": True}


    # =========================
    # BAYARGG WEBHOOK
    # =========================
    logging.info("💰 BAYARGG CHECK")

    if x_signature:
        if not verify_signature(body, x_signature):
            logging.warning("❌ INVALID SIGNATURE")
            return {"ok": True}
    else:
        logging.warning("⚠️ NO SIGNATURE (DEV MODE)")


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

    logging.info(f"📌 STATUS: {status}")
    logging.info(f"📌 REF: {ref}")

    if not status or not is_paid(status):
        logging.info("⏳ NOT PAID / EMPTY")
        return {"ok": True}


    # =========================
    # DB CONNECTION
    # =========================
    pool = await get_pool()

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
    # ANTI DUPLICATE (DB SAFE)
    # =========================
    updated = await pool.fetchval("""
        UPDATE payments
        SET status='paid'
        WHERE user_id=$1 AND code=$2 AND status='pending'
        RETURNING id
    """, user_id, code)

    if not updated:
        logging.warning("⚠️ ALREADY PROCESSED")
        return {"ok": True}


    # =========================
    # ACCESS GRANT
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


    # =========================
    # CALC REVENUE
    # =========================
    fee = int(price * 0.1)
    income = price - fee

    await pool.execute("""
        INSERT INTO users (telegram_id, balance)
        VALUES ($1,$2)
        ON CONFLICT (telegram_id)
        DO UPDATE SET balance = users.balance + EXCLUDED.balance
    """, seller_id, income)


    # =========================
    # NOTIFY USER
    # =========================
    try:
        await bot.send_message(
            user_id,
            f"""✅ PAYMENT SUCCESS

📦 CODE: {code}
📁 FILE: {len(media)}
🔐 ACCESS GRANTED"""
        )
    except Exception as e:
        logging.error(f"❌ NOTIFY ERROR: {e}")


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
        try:
            await bot.send_message(
                int(GROUP_ID),
                f"""💰 TRANSACTION SUCCESS

📦 CODE: {code}
👤 USER: {user_id}
💸 PRICE: {price}"""
            )
        except:
            pass


    logging.info(f"⚡ DONE {(datetime.utcnow() - start).total_seconds():.2f}s")

    return {"ok": True}
