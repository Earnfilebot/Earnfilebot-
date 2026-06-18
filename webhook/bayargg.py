import hmac
import hashlib
import json

from fastapi import APIRouter, Request, Header
from database import get_pool
from bot import bot

router = APIRouter()

BAYARGG_SECRET = "whsec_81c259f2d3291e377957b7b56155683290aacc63e41a0df2"


# =========================
# SAFE PARSE REFERENCE
# =========================
def parse_reference(ref: str):
    try:
        user_id, code = ref.split("_", 1)
        return int(user_id), code
    except:
        return None, None


# =========================
# SIGNATURE VERIFY FIXED
# =========================
def verify_signature(payload: dict, signature: str):
    # IMPORTANT: normalize JSON
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()

    expected = hmac.new(
        BAYARGG_SECRET.encode(),
        raw,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# =========================
# WEBHOOK
# =========================
@router.post("/bayargg/webhook")
async def webhook(req: Request, x_signature: str = Header(None)):

    body = await req.body()
    data = json.loads(body.decode())
    payload = data.get("data", data)

    reference = payload.get("reference")
    status = payload.get("status")

    if status != "PAID":
        return {"ok": True}

    # 🔐 SIGNATURE CHECK
    expected = hmac.new(
        BAYARGG_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if x_signature and not hmac.compare_digest(expected, x_signature):
        return {"ok": False}

    user_id, code = parse_reference(reference)
    if not user_id:
        return {"ok": False}

    pool = await get_pool()

    # 🔒 ANTI DOUBLE PAYMENT (LOCK ROW)
    updated = await pool.fetchval("""
        UPDATE payments
        SET status='paid'
        WHERE user_id=$1 AND code=$2 AND status!='paid'
        RETURNING id
    """, user_id, code)

    if not updated:
        return {"ok": True}

    # 🔥 ambil file + seller
    file = await pool.fetchrow("""
        SELECT seller_id, price, media
        FROM files
        WHERE code=$1
    """, code)

    seller_id = file["seller_id"]
    price = int(file["price"])

    # =========================
    # FEE SYSTEM
    # =========================
    fee = int(price * 0.10)
    seller_income = price - fee

    # =========================
    # UPDATE BALANCE SELLER
    # =========================
    await pool.execute("""
        UPDATE users
        SET balance = balance + $1
        WHERE user_id=$2
    """, seller_income, seller_id)

    # =========================
    # TRANSACTION LOG
    # =========================
    await pool.execute("""
        INSERT INTO transactions(user_id, seller_id, code, amount, fee, status)
        VALUES($1,$2,$3,$4,$5,'paid')
    """, user_id, seller_id, code, price, fee)

    # =========================
    # SAVE ACCESS
    # =========================
    await pool.execute("""
        INSERT INTO user_access(user_id, code, paid)
        VALUES($1,$2,true)
        ON CONFLICT DO NOTHING
    """, user_id, code)

    # =========================
    # NOTIFY USER
    # =========================
    await bot.send_message(
        user_id,
        f"✅ PAYMENT SUCCESS\n🔓 CODE: {code}"
    )

    # =========================
    # CHANNEL LOG
    # =========================
    await bot.send_message(
        -1001234567890,
        f"💰 NEW SALE\n"
        f"📦 {code}\n"
        f"💸 {price}\n"
    )

    return {"ok": True}
