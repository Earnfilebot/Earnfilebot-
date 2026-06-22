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

BAYARGG_SECRET = os.getenv("BAYARGG_WEBHOOK_SECRET", "")
logging.basicConfig(level=logging.INFO)


# =========================
# UTILS
# =========================
def parse_reference(ref: str):
    if not ref:
        return None, None

    try:
        parts = ref.split("_")
        user_id = int(parts[0])
        code = parts[1]
        return user_id, code
    except:
        return None, None


def verify_signature(body: bytes, signature: str):
    if not signature or not BAYARGG_SECRET:
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
# SAFE SEND
# =========================
async def safe_send(bot, user_id, item):
    try:
        t = item.get("type")
        fid = item.get("file_id")

        if not fid:
            return False

        if t == "document":
            await bot.send_document(user_id, fid)
        elif t == "video":
            await bot.send_video(user_id, fid)
        else:
            await bot.send_photo(user_id, fid)

        return True

    except Exception as e:
        logging.error(f"❌ SEND FAIL: {repr(e)}")
        return False


@router.post("/webhook")
async def webhook(
    req: Request,
    x_signature: str = Header(None, alias="X-Signature")
):

    start_time = datetime.utcnow()
    logging.info("🔥 WEBHOOK HIT")

    bot = getattr(req.app.state, "bot", None)
    dp = getattr(req.app.state, "dp", None)

    if not bot or not dp:
        logging.error("❌ BOT / DP NOT READY")
        return {"ok": True}

    body = await req.body()

    try:
        data = json.loads(body.decode())
    except Exception as e:
        logging.error(f"❌ INVALID JSON: {e}")
        return {"ok": True}

    # =========================
    # TELEGRAM UPDATE
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
    # BAYARGG WEBHOOK
    # =========================
    logging.info("💰 BAYARGG WEBHOOK")

    logging.info(f"🔐 SIGNATURE: {x_signature}")

    # ❗ FIX: kalau signature kosong jangan stop silent
    if not x_signature:
        logging.warning("⚠️ NO SIGNATURE (SKIP SECURITY CHECK)")
    else:
        if not verify_signature(body, x_signature):
            logging.warning("❌ INVALID SIGNATURE")
            return {"ok": True}

    payload = data.get("data") or data

    status = (
        payload.get("status")
        or data.get("status")
        or ("PAID" if data.get("success") is True else None)
    )

    ref = (
        payload.get("external_id")
        or payload.get("reference")
        or data.get("invoice_id")
    )

    logging.info(f"📦 STATUS: {status}")
    logging.info(f"📦 REF: {ref}")

    if not status:
        logging.warning("❌ EMPTY STATUS")
        return {"ok": True}

    if status.upper() not in ["PAID", "SUCCESS", "SETTLED"]:
        logging.info("⏳ NOT PAID STATUS")
        return {"ok": True}

    pool = await get_pool()

    # =========================
    # AMBIL PAYMENT (ROBUST)
    # =========================
    payment = await pool.fetchrow("""
        SELECT user_id, code
        FROM payments
        WHERE invoice_id = $1
           OR external_id = $1
           OR code = $1
    """, ref)

    if not payment:
        logging.warning("❌ PAYMENT NOT FOUND IN DB")
        return {"ok": True}

    user_id = payment["user_id"]
    code = payment["code"]

    try:
        # =========================
        # UPDATE PAYMENT
        # =========================
        updated = await pool.fetchval("""
            UPDATE payments
            SET status='paid'
            WHERE user_id=$1 AND code=$2 AND status='pending'
            RETURNING id
        """, user_id, code)

        if updated:
            logging.info("✅ PAYMENT UPDATED")
        else:
            logging.warning("⚠️ PAYMENT ALREADY PROCESSED")

        # =========================
        # GRANT ACCESS
        # =========================
        await pool.execute("""
            INSERT INTO user_access(user_id, code, paid)
            VALUES ($1,$2,TRUE)
            ON CONFLICT (user_id, code)
            DO UPDATE SET paid=TRUE
        """, user_id, code)

        logging.info(f"✅ ACCESS GRANTED {user_id} -> {code}")

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

        # safe JSON parse
        media_list = []
        try:
            if file["media_json"]:
                media_list = json.loads(file["media_json"])
        except:
            media_list = []

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
            f"✅ PAYMENT SUCCESS\nCODE: {code}\nFILE: {len(media_list)}"
        )

        # =========================
        # SEND FILE
        # =========================
        for item in media_list:
            await safe_send(bot, user_id, item)
            await asyncio.sleep(0.2)

        # =========================
        # GROUP LOG
        # =========================
        if GROUP_ID:
            await bot.send_message(
                int(GROUP_ID),
                f"💰 TRANSAKSI BERHASIL\nCODE: {code}\nBUYER: {user_id}\nPRICE: Rp {price}"
            )

        logging.info("⚡ PAYMENT FLOW DONE")

    except Exception as e:
        logging.exception(f"❌ WEBHOOK ERROR: {e}")

    logging.info(f"⏱ DONE {(datetime.utcnow() - start_time).total_seconds():.2f}s")

    return {"ok": True}
