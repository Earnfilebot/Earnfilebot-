import hmac
import hashlib
from fastapi import APIRouter, Request, Header

from database import get_pool
from bot import bot

router = APIRouter()

BAYARGG_SECRET = "ISI_SECRET_KAMU"  # dari dashboard BayarGG


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
# VERIFY SIGNATURE (ANTI FAKE 🔴)
# =========================
def verify_signature(payload: dict, signature: str):
    raw = str(payload).encode()
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
    data = await req.json()

    payload = data.get("data", data)
    reference = payload.get("reference")
    status = payload.get("status")

    if not reference or not status:
        return {"ok": False}

    # 🔴 SECURITY CHECK
    if x_signature and not verify_signature(payload, x_signature):
        return {"ok": False, "error": "invalid signature"}

    user_id, code = parse_reference(reference)

    if not user_id or not code:
        return {"ok": False}

    if status.upper() != "PAID":
        return {"ok": True}

    pool = await get_pool()

    # 🔴 ANTI DUPLICATE RACE CONDITION
    updated = await pool.execute("""
        UPDATE payments
        SET status='paid'
        WHERE user_id=$1 AND code=$2 AND status!='paid'
    """, user_id, code)

    # kalau sudah pernah paid, stop
    if updated == "UPDATE 0":
        return {"ok": True}

    # =========================
    # AMBIL FILE
    # =========================
    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code=$1",
        code
    )

    if not file:
        return {"ok": False}

    media = file.get("media") or []

    if isinstance(media, str):
        import json
        media = json.loads(media)

    # =========================
    # 🔴 AUTO UNLOCK REAL TIME
    # =========================
    await bot.send_message(
        user_id,
        "✅ PAYMENT SUCCESS\n🔓 FILE UNLOCKED"
    )

    for m in media[:10]:
        try:
            await bot.send_document(user_id, m["file_id"])
        except:
            pass

    return {"ok": True}
