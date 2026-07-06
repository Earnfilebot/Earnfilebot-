import hmac
import hashlib
import logging

from fastapi import APIRouter, Request

from bot import bot
from database import get_pool
from utils.redis_client import redis_client
from config import BAYARGG_SECRET

router = APIRouter(prefix="/bayargg", tags=["BayarGG"])

BAYARGG_SECRET = BAYARGG_SECRET.encode()
ADMIN_CHAT_ID = -1004395938795


def secure_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a or "", b or "")


@router.post("/webhook")
async def webhook(request: Request):

    body = await request.body()
    signature = request.headers.get("X-Callback-Signature", "")

    expected = hmac.new(
        BAYARGG_SECRET,
        body,
        hashlib.sha256
    ).hexdigest()

    print("SIGNATURE:", signature)
    print("EXPECTED :", expected)

    if not secure_compare(signature, expected):
        print("INVALID SIGNATURE")
        return {"success": False, "message": "invalid signature"}

    try:
        data = await request.json()
    except Exception:
        return {"success": False, "message": "invalid json"}

    print("WEBHOOK DATA:", data)

    invoice_id = data.get("invoice_id")
    status = str(data.get("status", "")).lower()

    if not invoice_id:
        return {"success": False, "message": "missing invoice"}

    if status != "paid":
        print("STATUS BUKAN PAID:", status)
        return {"success": True, "message": "ignored"}

    redis_key = f"webhook:bayargg:{invoice_id}"

    try:
        if await redis_client.get(redis_key):
            return {"success": True, "message": "already processed"}

        await redis_client.set(redis_key, "1", ex=86400)
    except Exception:
        pass

    pool = await get_pool()

    tx = await pool.fetchrow(
        """
        SELECT user_id, file_code, status
        FROM file_purchases
        WHERE payment_id=$1
        """,
        invoice_id
    )

    if not tx:
        print("TRANSACTION NOT FOUND:", invoice_id)
        return {"success": False, "message": "not found"}

    if tx["status"] == "paid":
        return {"success": True, "message": "already paid"}

    await pool.execute(
        """
        UPDATE file_purchases
        SET status='paid',
            paid_at=NOW()
        WHERE payment_id=$1
        """,
        invoice_id
    )

    print("PAYMENT UPDATED:", invoice_id)

    try:
        await bot.send_message(
            tx["user_id"],
            "✅ <b>Pembayaran Berhasil!</b>\n\nFile kamu sudah aktif.",
            parse_mode="HTML"
        )

        await bot.send_message(
            ADMIN_CHAT_ID,
            (
                "💰 <b>PAYMENT SUCCESS</b>\n\n"
                f"🧾 Invoice: <code>{invoice_id}</code>\n"
                f"👤 User: <code>{tx['user_id']}</code>\n"
                f"📦 File: <code>{tx['file_code']}</code>"
            ),
            parse_mode="HTML"
        )

    except Exception:
        logging.exception("telegram notify failed")

    return {"success": True}
