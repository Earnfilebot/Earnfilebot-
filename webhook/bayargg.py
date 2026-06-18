import hmac
import hashlib
import json
import os
import logging

from fastapi import APIRouter, Request, Header
from database import get_pool
from config import GROUP_ID
from aiogram import Bot

router = APIRouter()

bot: Bot = None

BAYARGG_SECRET = os.getenv("BAYARGG_WEBHOOK_SECRET", "")

logging.basicConfig(level=logging.INFO)


# =========================
# PARSE REFERENCE
# =========================
def parse_reference(ref: str):
    try:
        user_id, code = ref.split("_", 1)
        return int(user_id), code
    except:
        return None, None


# =========================
# SIGNATURE VERIFY (ROBUST)
# =========================
def verify_signature(body: bytes, signature: str):

    if not signature or not BAYARGG_SECRET:
        return False

    expected = hmac.new(
        BAYARGG_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# =========================
# WEBHOOK
# =========================
@router.post("/bayargg/webhook")
async def webhook(req: Request, x_signature: str = Header(None)):

    body = await req.body()

    logging.info("Webhook hit received")

    # 🔐 SECURITY CHECK FIRST
    if not verify_signature(body, x_signature):
        logging.warning("Invalid signature rejected")
        return {"ok": False, "reason": "invalid signature"}

    try:
        data = json.loads(body.decode())
    except Exception as e:
        logging.error(f"JSON parse error: {e}")
        return {"ok": False}

    payload = data.get("data") or data

    reference = payload.get("reference")
    status = payload.get("status")

    if status != "PAID":
        return {"ok": True, "ignored": True}

    user_id, code = parse_reference(reference)

    if not user_id or not code:
        return {"ok": False, "reason": "invalid reference"}

    pool = await get_pool()

    # =========================
    # ATOMIC PAYMENT LOCK
    # =========================
    updated = await pool.fetchval("""
        UPDATE payments
        SET status='paid'
        WHERE user_id=$1
          AND code=$2
          AND status='pending'
        RETURNING id
    """, user_id, code)

    if not updated:
        logging.info("Duplicate webhook ignored")
        return {"ok": True}

    # =========================
    # GET FILE
    # =========================
    file = await pool.fetchrow("""
        SELECT seller_id, price
        FROM files
        WHERE code=$1
    """, code)

    if not file:
        logging.error("File not found in DB")
        return {"ok": False}

    seller_id = file["seller_id"]
    price = int(file["price"])

    # =========================
    # FEE SYSTEM
    # =========================
    fee = int(price * 0.10)
    seller_income = price - fee

    # =========================
    # UPDATE SELLER BALANCE
    # =========================
    await pool.execute("""
        UPDATE users
        SET balance = COALESCE(balance,0) + $1
        WHERE telegram_id=$2
    """, seller_income, seller_id)

    # =========================
    # TRANSACTION LOG
    # =========================
    await pool.execute("""
        INSERT INTO transactions(user_id, seller_id, code, amount, fee, status)
        VALUES($1,$2,$3,$4,$5,'paid')
    """, user_id, seller_id, code, price, fee)

    # =========================
    # UNLOCK ACCESS
    # =========================
    await pool.execute("""
        INSERT INTO user_access(user_id, code, paid)
        VALUES($1,$2,true)
        ON CONFLICT DO NOTHING
    """, user_id, code)

    # =========================
    # NOTIFY USER
    # =========================
    try:
        await bot.send_message(
            user_id,
            f"✅ PAYMENT SUCCESS\n\n"
            f"🔓 Code: {code}\n"
            f"💰 Paid: Rp {price}"
        )
    except Exception as e:
        logging.error(f"Notify user failed: {e}")

    # =========================
    # GROUP LOG
    # =========================
    try:
        await bot.send_message(
            GROUP_ID,
            f"💰 NEW SALE\n"
            f"📦 {code}\n"
            f"💸 Rp {price}\n"
            f"👤 User: {user_id}"
        )
    except Exception as e:
        logging.error(f"Group log failed: {e}")

    return {"ok": True}
