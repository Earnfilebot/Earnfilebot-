import hmac
import hashlib
from fastapi import APIRouter, Request

from bot import bot
from database import get_pool

router = APIRouter()

@router.post("/bayargg/webhook")
async def webhook(request: Request):

    body = await request.body()

    signature = request.headers.get("X-Callback-Signature", "")

    expected = hmac.new(
        b"YOUR_BAYARGG_SECRET",
        body,
        hashlib.sha256
    ).hexdigest()

    if signature != expected:
        return {"success": False}

    data = await request.json()

    invoice_id = data.get("invoice_id")
    status = data.get("status")

    if status != "paid":
        return {"success": True}

    pool = await get_pool()

    tx = await pool.fetchrow(
        "SELECT * FROM file_purchases WHERE payment_id=$1",
        invoice_id
    )

    if not tx:
        return {"success": False}

    if tx["status"] == "paid":
        return {"success": True}

    # =========================
    # UPDATE STATUS
    # =========================
    await pool.execute(
        """
        UPDATE file_purchases
        SET status='paid'
        WHERE payment_id=$1
        """,
        invoice_id
    )

    # =========================
    # TELEGRAM PUSH USER
    # =========================
    await bot.send_message(
        tx["user_id"],
        "✅ <b>Pembayaran Berhasil!</b>\nKlik untuk akses file",
        parse_mode="HTML",
        reply_markup=None
    )

    # =========================
    # TELEGRAM ADMIN LOG
    # =========================
    await bot.send_message(
        "ADMIN_CHAT_ID",
        f"💰 Paid: {invoice_id}\nUser: {tx['user_id']}\nFile: {tx['file_code']}"
    )

    return {"success": True}
