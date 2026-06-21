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
        user_id, code = ref.split("_", 1)
        return int(user_id), code
    except Exception:
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
# SAFE SEND FUNCTION
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


# =========================
# WEBHOOK
# =========================
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
            logging.info(f"📥 UPDATE => {data}")

            update = Update.model_validate(data)

            logging.info("⚡ FEED UPDATE START")

            await dp.feed_update(bot, update)

            logging.info("✅ UPDATE PROCESSED")

        except Exception as e:
            logging.exception(f"❌ TELEGRAM ERROR: {e}")

        return {"ok": True}

    # =========================
    # BAYARGG WEBHOOK
    # =========================
    logging.info("💰 BAYARGG WEBHOOK")

    if not verify_signature(body, x_signature):
        logging.warning("❌ INVALID SIGNATURE")
        return {"ok": True}

    payload = data.get("data") or data
    status = payload.get("status")
    ref = payload.get("reference")

    if not is_paid_status(status):
        return {"ok": True}

    user_id, code = parse_reference(ref)

    if not user_id or not code:
        return {"ok": True}

    pool = await get_pool()

    try:
        payment_id = await pool.fetchval("""
            UPDATE payments
            SET status='paid'
            WHERE user_id=$1 AND code=$2 AND status='pending'
            RETURNING id
        """, user_id, code)

        if not payment_id:
            logging.warning("⚠️ payment_id not found (continue safe)")

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

        # SAFE PARSE MEDIA
        try:
            media_list = json.loads(file["media_json"]) if isinstance(file["media_json"], str) else (file["media_json"] or [])
        except Exception:
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
        # SEND NOTIF USER
        # =========================
        await bot.send_message(
            user_id,
            f"""✅ PEMBAYARAN BERHASIL

📦 Kode : {code}
📁 Total File : {len(media_list)}
🔐 Akses aktif"""
        )

        # =========================
        # SEND MEDIA (SAFE LOOP)
        # =========================
        sent = 0

        for item in media_list:
            ok = await safe_send(bot, user_id, item)
            if ok:
                sent += 1
            await asyncio.sleep(0.4)

        logging.info(f"📤 MEDIA SENT: {sent}/{len(media_list)}")

    except Exception as e:
        logging.exception(f"❌ DB ERROR: {e}")
        return {"ok": True}

    # =========================
    # GROUP LOG
    # =========================
    try:
        if GROUP_ID:
            await bot.send_message(
                int(GROUP_ID),
                f"""💰 TRANSAKSI BERHASIL

📦 Produk : {code}
💸 Harga : Rp {price:,}
👤 Buyer : {user_id}
🏷 Seller : {seller_id}"""
            )
    except Exception as e:
        logging.error(f"GROUP ERROR: {e}")

    logging.info(f"⚡ DONE {(datetime.utcnow() - start_time).total_seconds():.2f}s")

    return {"ok": True}
