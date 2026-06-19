import hmac
import hashlib
import json
import os
import logging

from fastapi import APIRouter, Request, Header
from database import get_pool
from config import GROUP_ID

router = APIRouter()

BAYARGG_SECRET = os.getenv("BAYARGG_WEBHOOK_SECRET", "")

logging.basicConfig(level=logging.INFO)


def parse_reference(ref: str):
    try:
        user_id, code = ref.split("_", 1)
        return int(user_id), code
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


@router.post("/webhook")
async def webhook(req: Request, x_signature: str = Header(None)):

    bot = req.app.state.bot
    body = await req.body()

    logging.info("📩 Webhook received")

    if not verify_signature(body, x_signature):
        logging.warning("❌ Invalid signature")
        return {"ok": True}

    try:
        data = json.loads(body.decode())
    except Exception as e:
        logging.error(f"JSON error: {e}")
        return {"ok": True}

    payload = data.get("data") or data

    if payload.get("status") != "PAID":
        return {"ok": True}

    user_id, code = parse_reference(payload.get("reference"))

    if not user_id or not code:
        logging.warning("❌ Invalid reference")
        return {"ok": True}

    pool = await get_pool()

    updated = await pool.fetchval("""
        UPDATE payments
        SET status='paid'
        WHERE user_id=$1 AND code=$2 AND status='pending'
        RETURNING id
    """, user_id, code)

    if not updated:
        logging.info("⚠️ Already processed")
        return {"ok": True}

    file = await pool.fetchrow("""
        SELECT seller_id, price, media_json
        FROM files
        WHERE code=$1
    """, code)

    if not file:
        logging.error(f"❌ FILE NOT FOUND: {code}")
        return {"ok": True}

    seller_id = file["seller_id"]
    price = int(file["price"])
    media_json = file["media_json"]

    fee = int(price * 0.10)
    seller_income = price - fee

    logging.info(f"SELLER: {seller_id} | INCOME: {seller_income}")

    # ✅ UPSERT BALANCE (AMAN)
    await pool.execute("""
        INSERT INTO users (telegram_id, balance)
        VALUES ($1, $2)
        ON CONFLICT (telegram_id)
        DO UPDATE SET balance = users.balance + $2
    """, seller_id, seller_income)

    await pool.execute("""
        INSERT INTO transactions(user_id, seller_id, code, amount, fee, status)
        VALUES($1,$2,$3,$4,$5,'paid')
        ON CONFLICT DO NOTHING
    """, user_id, seller_id, code, price, fee)

    await pool.execute("""
        INSERT INTO user_access(user_id, code, paid)
        VALUES($1,$2,true)
        ON CONFLICT DO NOTHING
    """, user_id, code)

    logging.info(f"💰 PAID SUCCESS: {user_id} | {code}")

    # =========================
    # SEND FILE
    # =========================
    try:
        if isinstance(media_json, str):
            media_list = json.loads(media_json)
        else:
            media_list = media_json

        logging.info(f"MEDIA: {media_list}")

        await bot.send_message(
            user_id,
            f"✅ PAYMENT SUCCESS\n📦 {code}\n📁 {len(media_list)} file"
        )

        for item in media_list:
            file_id = item.get("file_id")
            media_type = item.get("type")

            if media_type == "document":
                await bot.send_document(user_id, file_id)
            elif media_type == "video":
                await bot.send_video(user_id, file_id)
            elif media_type == "photo":
                await bot.send_photo(user_id, file_id)

    except Exception as e:
        logging.exception(f"SEND FILE ERROR: {e}")

    # =========================
    # GROUP LOG
    # =========================
    try:
        if GROUP_ID:
            await bot.send_message(
                GROUP_ID,
                f"💰 SALE\n📦 {code}\n💸 Rp {price:,}\n👤 {user_id}"
            )
    except Exception as e:
        logging.error(f"GROUP ERROR: {e}")

    return {"ok": True}
