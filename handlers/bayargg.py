import hmac
import hashlib
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot import bot
from config import BAYARGG_API_KEY, CHANNEL_ID
from config_vip import VIP_PACKAGES
from database import get_pool
from utils.redis_client import redis_client
from handlers.page import send_page

router = APIRouter(prefix="/bayargg", tags=["BayarGG"])


def secure_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a or "", b or "")


@router.post("/webhook")
async def bayargg_webhook(request: Request):

    body = await request.body()
    signature = request.headers.get("X-Callback-Signature", "")

    expected = hmac.new(
        BAYARGG_API_KEY.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not secure_compare(signature, expected):
        return {"success": False, "message": "invalid signature"}

    data = await request.json()

    invoice_id = data.get("invoice_id")
    status = (data.get("status") or "").lower()

    if not invoice_id:
        return {"success": False, "message": "missing invoice"}

    if status != "paid":
        return {"success": True, "message": "ignored"}

    logging.info(f"🔥 WEBHOOK: {invoice_id} - {status}")

    # =========================
    # IDEMPOTENCY LOCK
    # =========================
    redis_key = f"webhook:processed:{invoice_id}"

    if await redis_client.get(redis_key):
        return {"success": True, "message": "already processed"}

    await redis_client.set(redis_key, "1", ex=86400, nx=True)

    pool = await get_pool()

    # =====================================================
    # FILE PAYMENT
    # =====================================================
    purchase = await pool.fetchrow(
        "SELECT * FROM file_purchases WHERE payment_id=$1",
        invoice_id
    )

    if purchase:

        if purchase["status"] == "paid":
            return {"success": True}

        await pool.execute(
            """
            UPDATE file_purchases
            SET status='paid',
                paid_at=NOW()
            WHERE payment_id=$1
            """,
            invoice_id
        )

        await redis_client.delete(f"invoice:{invoice_id}")

        try:
            await bot.send_message(
                purchase["user_id"],
                "✅ <b>Pembayaran berhasil!</b>\n\n📦 File sedang dikirim...",
                parse_mode="HTML"
            )

            success = await send_page(
                bot=bot,
                chat_id=purchase["user_id"],
                user_id=purchase["user_id"],
                code=purchase["file_code"],
                page=1
            )

            if success:
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📂 OPEN FILE",
                                callback_data=f"page:{purchase['file_code']}:1"
                            )
                        ]
                    ]
                )

                await bot.send_message(
                    purchase["user_id"],
                    "📦 File berhasil dikirim.\nJika ingin membukanya lagi silakan tekan tombol di bawah.",
                    reply_markup=kb
                )
            else:
                await bot.send_message(
                    purchase["user_id"],
                    "❌ File gagal dikirim, silakan hubungi admin."
                )

        except Exception:
            logging.exception("file notify failed")

        return {"success": True}

    # =====================================================
    # VIP PAYMENT
    # =====================================================
    trx = await pool.fetchrow(
        "SELECT * FROM payments WHERE invoice_id=$1",
        invoice_id
    )

    if not trx:
        return {"success": False, "message": "not found"}

    if trx["status"] == "paid":
        return {"success": True}

    paket = VIP_PACKAGES.get(trx["code"])
    if not paket:
        return {"success": False, "message": "invalid package"}

    user = await pool.fetchrow(
        "SELECT vip_until FROM users WHERE telegram_id=$1",
        trx["user_id"]
    )

    now = datetime.now(timezone.utc)

    vip_until = (
        user["vip_until"] + timedelta(days=paket["days"])
        if user and user["vip_until"] and user["vip_until"] > now
        else now + timedelta(days=paket["days"])
    )

    async with pool.acquire() as conn:
        async with conn.transaction():

            await conn.execute(
                "UPDATE payments SET status='paid' WHERE invoice_id=$1",
                invoice_id
            )

            await conn.execute(
                """
                UPDATE users
                SET vip=TRUE,
                    is_vip=TRUE,
                    vip_until=$1
                WHERE telegram_id=$2
                """,
                vip_until,
                trx["user_id"]
            )

    try:
        await bot.send_message(
            trx["user_id"],
            f"🎉 VIP ACTIVE\n\n"
            f"Paket : {paket['name']}\n"
            f"Expired : {vip_until:%d-%m-%Y %H:%M UTC}"
        )

        await bot.send_message(
            CHANNEL_ID,
            f"💎 VIP SOLD\n"
            f"User : {trx['user_id']}\n"
            f"Plan : {paket['name']}"
        )

    except Exception:
        logging.exception("vip notify failed")

    return {"success": True}
        logging.exception("vip notify failed")

    return {"success": True}
