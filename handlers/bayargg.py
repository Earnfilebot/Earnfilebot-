import hmac
import hashlib
import logging

from fastapi import APIRouter, Request

from bot import bot
from config import BAYARGG_API_KEY
from database import get_pool
from config_vip import VIP_PACKAGES

from datetime import datetime, timedelta, timezone

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

    paket = VIP_PACKAGES[trx["code"]]

    vip_until = datetime.now(timezone.utc) + timedelta(
        days=paket["days"]
    )

    # =========================
    # UPDATE PAYMENT
    # =========================
    await pool.execute(
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
    await pool.execute(
        """
        UPDATE users
        SET
            vip=true,
            is_vip=true,
            vip_until=$1
        WHERE telegram_id=$2
        """,
        vip_until,
        trx["user_id"]
    )

    # =========================
    # VIP HISTORY
    # =========================
    await pool.execute(
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
