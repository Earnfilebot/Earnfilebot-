import hmac
import hashlib
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request

from bot import bot
from config import BAYARGG_API_KEY
from config_vip import VIP_PACKAGES
from database import get_pool

router = APIRouter(prefix="/bayargg", tags=["BayarGG"])


@router.post("/webhook")
async def bayargg_webhook(request: Request):

    body = await request.body()

    # =========================
    # VERIFY SIGNATURE
    # =========================
    signature = request.headers.get("X-Callback-Signature", "")

    expected = hmac.new(
        BAYARGG_API_KEY.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if signature != expected:
        return {
            "success": False,
            "message": "invalid signature"
        }

    data = await request.json()

    invoice_id = data.get("invoice_id")
    status = data.get("status", "").lower()

    if status != "paid":
        return {
            "success": True,
            "message": "ignored"
        }

    pool = await get_pool()

    trx = await pool.fetchrow(
        """
        SELECT *
        FROM payments
        WHERE invoice_id=$1
        """,
        invoice_id
    )

    if not trx:
        return {
            "success": False,
            "message": "invoice not found"
        }

    if trx["status"] == "paid":
        return {
            "success": True,
            "message": "already processed"
        }

    paket = VIP_PACKAGES.get(trx["code"])

    if not paket:
        return {
            "success": False,
            "message": "invalid package"
        }

    user = await pool.fetchrow(
        """
        SELECT vip_until
        FROM users
        WHERE telegram_id=$1
        """,
        trx["user_id"]
    )

    now = datetime.now(timezone.utc)

    if user and user["vip_until"] and user["vip_until"] > now:
        vip_until = user["vip_until"] + timedelta(days=paket["days"])
    else:
        vip_until = now + timedelta(days=paket["days"])

    async with pool.acquire() as conn:
        async with conn.transaction():

            # =========================
            # UPDATE PAYMENT
            # =========================
            await conn.execute(
                """
                UPDATE payments
                SET
                    status='paid',
                    updated_at=NOW()
                WHERE invoice_id=$1
                """,
                invoice_id
            )

            # =========================
            # UPDATE USER
            # =========================
            await conn.execute(
                """
                UPDATE users
                SET
                    vip=TRUE,
                    is_vip=TRUE,
                    vip_until=$1
                WHERE telegram_id=$2
                """,
                vip_until,
                trx["user_id"]
            )

            # =========================
            # VIP HISTORY
            # =========================
            await conn.execute(
                """
                INSERT INTO vip_users
                (
                    user_id,
                    plan,
                    invoice_id,
                    started_at,
                    expires_at,
                    active
                )
                VALUES
                ($1,$2,$3,NOW(),$4,TRUE)
                """,
                trx["user_id"],
                paket["name"],
                invoice_id,
                vip_until
            )

    # =========================
    # SEND TELEGRAM
    # =========================
    try:
        await bot.send_message(
            trx["user_id"],
            (
                "🎉 <b>Pembayaran Berhasil</b>\n\n"
                f"💎 Paket : <b>{paket['name']}</b>\n"
                f"📅 Berlaku sampai:\n"
                f"<code>{vip_until}</code>\n\n"
                "Selamat menikmati fitur VIP ❤️"
            ),
            parse_mode="HTML"
        )
    except Exception:
        logging.exception("Gagal mengirim pesan VIP")

    return {
        "success": True
    }
