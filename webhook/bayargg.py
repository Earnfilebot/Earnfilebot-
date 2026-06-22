import json
import logging
import hmac
import hashlib
import os
import asyncio

from fastapi import APIRouter, Request, Header

from database import get_pool

router = APIRouter()

SECRET = os.getenv("BAYARGG_SECRET", "")


# =========================
# SECURITY
# =========================
def verify_signature(body: bytes, signature: str):
    if not signature or not SECRET:
        return True  # biar tidak block saat dev

    expected = hmac.new(
        SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def is_paid(status: str):
    return status and status.upper() in ["PAID", "SUCCESS", "SETTLED"]


# =========================
# WEBHOOK
# =========================
@router.post("/webhook")
async def bayargg_webhook(
    req: Request,
    x_signature: str = Header(None, alias="X-Signature")
):

    logging.info("🔥 WEBHOOK HIT")

    body = await req.body()

    try:
        data = json.loads(body)
    except:
        logging.error("❌ INVALID JSON")
        return {"ok": True}

    # SIGNATURE CHECK
    if not verify_signature(body, x_signature):
        logging.warning("❌ INVALID SIGNATURE")
        return {"ok": True}

    payload = data.get("data") or data

    status = payload.get("status") or data.get("status")
    ref = payload.get("external_id") or data.get("invoice_id")

    logging.info(f"📦 STATUS={status}")
    logging.info(f"📦 REF={ref}")

    if not is_paid(status):
        return {"ok": True}

    pool = await get_pool()

    # =========================
    # FIND PAYMENT (ANTI ERROR)
    # =========================
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
    # GRANT ACCESS
    # =========================
    await pool.execute("""
        INSERT INTO user_access(user_id, code, paid)
        VALUES ($1,$2,TRUE)
        ON CONFLICT (user_id, code)
        DO UPDATE SET paid=TRUE
    """, user_id, code)

    logging.info(f"✅ PAID SUCCESS {user_id} {code}")

    # OPTIONAL: async delay safe
    asyncio.create_task(send_user_notification(user_id, code))

    return {"ok": True}


# =========================
# OPTIONAL BOT NOTIFY (SAFE)
# =========================
async def send_user_notification(user_id, code):
    try:
        from bot import bot

        await bot.send_message(
            user_id,
            f"✅ PAYMENT SUCCESS\nCODE: {code}"
        )
    except Exception as e:
        logging.error(f"❌ NOTIFY ERROR: {repr(e)}")
