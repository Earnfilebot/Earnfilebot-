import hmac
import hashlib
import logging

from fastapi import APIRouter, Request

from bot import bot
from database import get_pool
from utils.redis_client import redis_client

router = APIRouter(prefix="/bayargg", tags=["BayarGG"])

# =========================
# CONFIG
# =========================
BAYARGG_SECRET = b"YOUR_BAYARGG_SECRET"
ADMIN_CHAT_ID = "ADMIN_CHAT_ID"


# =========================
# SECURE COMPARE
# =========================
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

    # =========================
    # SIGNATURE CHECK
    # =========================
    if not secure_compare(signature, expected):
        return {"success": False, "message": "invalid signature"}

    data = await request.json()

    invoice_id = data.get("invoice_id")
    status = (data.get("status") or "").lower()

    if not invoice_id:
        return {"success": False, "message": "missing invoice"}

    if status != "paid":
        return {"success": True, "message": "ignored"}

    # =========================
    # 🔥 IDEMPOTENCY LOCK (ANTI DOUBLE WEBHOOK)
    # =========================
    redis_key = f"webhook:bayargg:{invoice_id}"
    if await redis_client.get(redis_key):
        return {"success": True, "message": "already processed"}

    await redis_client.set(redis_key, "1", ex=86400)

    pool = await get_pool()

    # =========================
    # GET TRANSACTION
    # =========================
    tx = await pool.fetchrow(
        "SELECT * FROM file_purchases WHERE payment_id=$1",
        invoice_id
    )

    if not tx:
        return {"success": False, "message": "not found"}

    # =========================
    # IDEMPOTENT CHECK DB
    # =========================
    if tx["status"] == "paid":
        return {"success": True, "message": "already paid"}

    # =========================
    # UPDATE DATABASE
    # =========================
    async with pool.acquire() as conn:
        async with conn.transaction():

            await conn.execute(
                """
                UPDATE file_purchases
                SET status='paid',
                    paid_at=NOW()
                WHERE payment_id=$1
                """,
                invoice_id
            )

    # =========================
    # TELEGRAM USER NOTIFY
    # =========================
    try:
        await bot.send_message(
            tx["user_id"],
            (
                "✅ <b>Pembayaran Berhasil!</b>\n\n"
                "File kamu sudah terbuka.\n"
                "Klik tombol di menu file."
            ),
            parse_mode="HTML"
        )

        # =========================
        # ADMIN LOG
        # =========================
        await bot.send_message(
            ADMIN_CHAT_ID,
            (
                "💰 <b>PAYMENT SUCCESS</b>\n\n"
                f"🧾 Invoice: <code>{invoice_id}</code>\n"
                f"👤 User: <code>{tx['user_id']}</code>\n"
                f"📦 File: <code>{tx['file_code']}</code>\n"
                f"💵 Status: PAID"
            ),
            parse_mode="HTML"
        )

    except Exception:
        logging.exception("telegram notify failed")

    return {"success": True}
