import hmac
import hashlib
import json
import os

from fastapi import APIRouter, Request, Header
from database import get_pool
from config import BAYARGG_API_KEY
from bot import bot

router = APIRouter()

# 🔐 MOVE TO ENV (WAJIB)
BAYARGG_SECRET = os.getenv("BAYARGG_WEBHOOK_SECRET", "")


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
# SAFE SIGNATURE VERIFY
# =========================
def verify_signature(raw_body: bytes, signature: str):

    if not signature:
        return False

    expected = hmac.new(
        BAYARGG_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# =========================
# WEBHOOK
# =========================
@router.post("/bayargg/webhook")
async def webhook(req: Request, x_signature: str = Header(None)):

    body = await req.body()

    # =========================
    # VERIFY SIGNATURE FIRST (SECURITY)
    # =========================
    if not verify_signature(body, x_signature):
        return {"ok": False, "reason": "invalid signature"}

    # =========================
    # PARSE JSON SAFE
    # =========================
    try:
        data = json.loads(body.decode())
    except:
        return {"ok": False, "reason": "invalid json"}

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
    # 🔥 HARD ANTI DOUBLE (ATOMIC LOCK)
    # =========================
    updated = await pool.fetchval("""
        UPDATE payments
        SET status='paid'
        WHERE user_id=$1 AND code=$2 AND status='pending'
        RETURNING id
    """, user_id, code)

    if not updated:
        return {"ok": True, "duplicate ignored"}

    # =========================
    # GET FILE
    # =========================
    file = await pool.fetchrow("""
        SELECT seller_id, price
        FROM files
        WHERE code=$1
    """, code)

    if not file:
        return {"ok": False, "reason": "file not found"}

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
    except:
        pass

    # =========================
    # LOG GROUP (SAFE)
    # =========================
    try:
        await bot.send_message(
            -1001234567890,
            f"💰 NEW SALE\n"
            f"📦 {code}\n"
            f"💸 Rp {price}\n"
            f"👤 User: {user_id}"
        )
    except:
        pass

    return {"ok": True}
