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


@router.post("/bayargg/webhook")
async def webhook(req: Request, x_signature: str = Header(None)):

    bot = req.app.state.bot  # 🔥 INI FIX UTAMA

    body = await req.body()

    logging.info("Webhook hit received")

    if not verify_signature(body, x_signature):
        return {"ok": False}

    try:
        data = json.loads(body.decode())
    except:
        return {"ok": False}

    payload = data.get("data") or data

    if payload.get("status") != "PAID":
        return {"ok": True}

    user_id, code = parse_reference(payload.get("reference"))

    if not user_id or not code:
        return {"ok": False}

    pool = await get_pool()

    updated = await pool.fetchval("""
        UPDATE payments
        SET status='paid'
        WHERE user_id=$1 AND code=$2 AND status='pending'
        RETURNING id
    """, user_id, code)

    if not updated:
        return {"ok": True}

    file = await pool.fetchrow("""
        SELECT seller_id, price
        FROM files
        WHERE code=$1
    """, code)

    if not file:
        return {"ok": False}

    seller_id = file["seller_id"]
    price = int(file["price"])

    fee = int(price * 0.10)
    seller_income = price - fee

    await pool.execute("""
        UPDATE users
        SET balance = COALESCE(balance,0) + $1
        WHERE telegram_id=$2
    """, seller_income, seller_id)

    await pool.execute("""
        INSERT INTO transactions(user_id, seller_id, code, amount, fee, status)
        VALUES($1,$2,$3,$4,$5,'paid')
    """, user_id, seller_id, code, price, fee)

    await pool.execute("""
        INSERT INTO user_access(user_id, code, paid)
        VALUES($1,$2,true)
        ON CONFLICT DO NOTHING
    """, user_id, code)

    try:
        await bot.send_message(
            user_id,
            f"✅ PAYMENT SUCCESS\n🔓 {code}\n💰 Rp {price}"
        )

        await bot.send_message(
            GROUP_ID,
            f"💰 NEW SALE\n📦 {code}\n💸 Rp {price}\n👤 {user_id}"
        )
    except Exception as e:
        logging.error(f"notify error: {e}")

    return {"ok": True}
