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

print("🔥 BAYARGG WEBHOOK PRODUCTION READY LOADED")

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
    if not status:
        return False
    return status.upper() in ["PAID", "SUCCESS", "SETTLED"]

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

    # =========================
    # PARSE JSON SAFELY
    # =========================
    try:
        data = json.loads(body.decode())
    except Exception as e:
        logging.error(f"❌ INVALID JSON: {e}")
        return {"ok": True}

    # =========================
    # TELEGRAM UPDATE
    # =========================
    if "update_id" in data and not x_signature:
        logging.info("🤖 TELEGRAM UPDATE")

        try:
            update = Update.model_validate(data)
            await dp.feed_update(bot, update)
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

    logging.info(f"STATUS={status} REF={ref}")

    if not is_paid_status(status):
        logging.info("⛔ STATUS NOT PAID")
        return {"ok": True}

    user_id, code = parse_reference(ref)

    if not user_id or not code:
        logging.warning("❌ INVALID REFERENCE FORMAT")
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
            logging.warning("❌ PAYMENT ALREADY PROCESSED")
            return {"ok": True}

        logging.info(f"✅ PAYMENT ID={payment_id}")

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
        price = int(file["price"])
        media_json = file["media_json"]

        fee = int(price * 0.10)
        seller_income = price - fee

        # =========================
        # UPDATE SELLER BALANCE
        # =========================
        await pool.execute("""
            INSERT INTO users (telegram_id, balance)
            VALUES ($1, $2)
            ON CONFLICT (telegram_id)
            DO UPDATE SET balance = users.balance + EXCLUDED.balance
        """, seller_id, seller_income)

        # =========================
        # NOTIFY SELLER
        # =========================
        try:
            await bot.send_message(
                seller_id,
                f"""💰 PENJUALAN BERHASIL

📦 Produk : {code}
💸 Harga : Rp {price:,}
📊 Fee : Rp {fee:,}
✅ Kamu terima : Rp {seller_income:,}
━━━━━━━━━━━━━━"""
            )
        except Exception as e:
            logging.error(f"SELLER NOTIF ERROR: {e}")

        # =========================
        # TRANSACTION LOG
        # =========================
        await pool.execute("""
            INSERT INTO transactions(user_id, seller_id, code, amount, fee, status)
            VALUES($1,$2,$3,$4,$5,'paid')
            ON CONFLICT DO NOTHING
        """, user_id, seller_id, code, price, fee)

        # =========================
        # ACCESS GRANT
        # =========================
        await pool.execute("""
            INSERT INTO user_access(user_id, code, paid)
            VALUES($1,$2,true)
            ON CONFLICT DO NOTHING
        """, user_id, code)

    except Exception as e:
        logging.exception(f"❌ DB ERROR: {e}")
        return {"ok": True}

    # =========================
    # SEND FILE
    # =========================
    try:
        try:
            media_list = json.loads(media_json) if isinstance(media_json, str) else (media_json or [])
        except Exception:
            media_list = []

        await bot.send_message(
            user_id,
            f"""✅ PEMBAYARAN BERHASIL

📦 Kode : {code}
📁 Total File : {len(media_list)}
🔐 Status : Akses diberikan

━━━━━━━━━━━━━━
📥 File akan dikirim otomatis..."""
        )

        for item in media_list:
            try:
                t = item.get("type")
                fid = item.get("file_id")

                if t == "document":
                    await bot.send_document(user_id, fid)
                elif t == "video":
                    await bot.send_video(user_id, fid)
                elif t == "photo":
                    await bot.send_photo(user_id, fid)

                await asyncio.sleep(0.4)

            except Exception as e:
                logging.error(f"SEND ERROR: {e}")

    except Exception as e:
        logging.exception(f"FILE SEND ERROR: {e}")

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
🏷 Seller : {seller_id}

━━━━━━━━━━━━━━
🔥 Media berhasil dikirim"""
            )
    except Exception as e:
        logging.error(f"GROUP ERROR: {e}")

    # =========================
    # DONE
    # =========================
    duration = (datetime.utcnow() - start_time).total_seconds()
    logging.info(f"⚡ DONE {duration:.2f}s")

    return {"ok": True}

