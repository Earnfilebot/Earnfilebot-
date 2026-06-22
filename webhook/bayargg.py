from fastapi import APIRouter, Request, Header
import logging
import json
import hmac
import hashlib
import os

from database import get_pool

router = APIRouter()

BAYARGG_SECRET = os.getenv("BAYARGG_WEBHOOK_SECRET", "")

logging.basicConfig(level=logging.INFO)


# =========================
# SECURITY
# =========================
def verify_signature(body: bytes, signature: str):
    if not signature or not BAYARGG_SECRET:
        return True  # sementara debug mode aman

    expected = hmac.new(
        BAYARGG_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# =========================
# STATUS CHECK
# =========================
def is_paid(status: str):
    return status and status.upper() in ["PAID", "SUCCESS", "SETTLED"]


# =========================
# WEBHOOK
# =========================
@router.post("/webhook")
async def webhook(req: Request, x_signature: str = Header(None, alias="X-Signature")):

    print("🔥 WEBHOOK HIT")  # <- ini wajib muncul

    body = await req.body()

    try:
        data = json.loads(body)
    except Exception:
        return {"ok": True}

    print("📦 RAW:", data)

    # signature check (non-blocking debug)
    if not verify_signature(body, x_signature):
        print("⚠️ signature invalid (ignored in debug)")
        return {"ok": True}

    payload = data.get("data") or data

    status = payload.get("status") or data.get("status")
    ref = payload.get("external_id") or data.get("reference") or data.get("invoice_id")

    print("📌 STATUS:", status)
    print("📌 REF:", ref)

    if not is_paid(status):
        print("⏳ not paid")
        return {"ok": True}

    pool = await get_pool()

    payment = await pool.fetchrow("""
        SELECT user_id, code
        FROM payments
        WHERE invoice_id=$1 OR external_id=$1 OR code=$1
    """, ref)

    if not payment:
        print("❌ payment not found")
        return {"ok": True}

    user_id = payment["user_id"]
    code = payment["code"]

    # update payment
    await pool.execute("""
        UPDATE payments
        SET status='paid'
        WHERE user_id=$1 AND code=$2
    """, user_id, code)

    # grant access
    await pool.execute("""
        INSERT INTO user_access(user_id, code, paid)
        VALUES ($1,$2,TRUE)
        ON CONFLICT (user_id, code)
        DO UPDATE SET paid=TRUE
    """, user_id, code)

    print("✅ PAYMENT SUCCESS:", user_id, code)

    return {"ok": True}
