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
async def bayargg_webhook(req: Request, x_signature: str = Header(None)):

    body = await req.body()
    data = json.loads(body.decode())
    payload = data.get("data", data)

    reference = payload.get("reference")
    status = payload.get("status")

    if not reference or not status:
        return {"ok": False}

    # =========================
    # SIGNATURE CHECK
    # =========================
    if x_signature:
        expected = hmac.new(
            BAYARGG_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, x_signature):
            return {"ok": False, "error": "invalid signature"}

    user_id, code = parse_reference(reference)
    if not user_id or not code:
        return {"ok": False}

    if status.upper() != "PAID":
        return {"ok": True}

    pool = await get_pool()

    # =========================
    # ANTI DOUBLE PAYMENT
    # =========================
    updated = await pool.execute("""
        UPDATE payments
        SET status='paid'
        WHERE user_id=$1 AND code=$2 AND status!='paid'
    """, user_id, code)

    if updated == "UPDATE 0":
        return {"ok": True}

    # =========================
    # CEK DUPLICATE TRANSACTION (FIXED POSITION)
    # =========================
    sent = await pool.fetchval("""
        SELECT 1 FROM transactions
        WHERE user_id=$1 AND code=$2
    """, user_id, code)

    if sent:
        return {"ok": True}

    # =========================
    # AMBIL FILE
    # =========================
    file = await pool.fetchrow("""
        SELECT seller_id, price, media
        FROM files
        WHERE code=$1
    """, code)

    if not file:
        return {"ok": False}

    seller_id = file["seller_id"]
    price = int(file["price"] or 0)

    media = file["media"]
    if isinstance(media, str):
        try:
            media = json.loads(media)
        except:
            media = []

    if not isinstance(media, list):
        media = []

    # =========================
    # HITUNG FEE
    # =========================
    admin_fee = int(price * 0.10)
    seller_income = price - admin_fee

    # =========================
    # UPDATE SALDO SELLER
    # =========================
    await pool.execute("""
        UPDATE users
        SET balance = balance + $1
        WHERE user_id = $2
    """, seller_income, seller_id)

    # =========================
    # SAVE ACCESS USER
    # =========================
    await pool.execute("""
        INSERT INTO user_access(user_id, code, paid)
        VALUES($1,$2,true)
        ON CONFLICT (user_id, code) DO UPDATE SET paid=true
    """, user_id, code)

    # =========================
    # INSERT TRANSACTION
    # =========================
    await pool.execute("""
        INSERT INTO transactions(user_id, seller_id, code, amount, fee, status)
        VALUES($1,$2,$3,$4,$5,'paid')
    """, user_id, seller_id, code, price, admin_fee)

    # =========================
    # NOTIFY USER
    # =========================
    await bot.send_message(
        user_id,
        f"✅ PAYMENT SUCCESS\n🔓 CODE: {code}"
    )

    # =========================
    # POST KE CHANNEL
    # =========================
    CHANNEL_ID = -1001234567890

    await bot.send_message(
        CHANNEL_ID,
        f"💰 NEW SALE\n"
        f"📦 CODE: {code}\n"
        f"👤 USER: {user_id}\n"
        f"💸 PRICE: {price}\n"
        f"🏦 SELLER EARN: {seller_income}\n"
        f"🧾 FEE: {admin_fee}"
    )

    # =========================
    # SEND FILE
    # =========================
    for m in media[:10]:
        try:
            fid = m.get("file_id")
            if fid:
                await bot.send_document(user_id, fid)
        except:
            pass

    return {"ok": True}
