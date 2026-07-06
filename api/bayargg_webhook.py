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

    if not secure_compare(signature, expected):
        return {"success": False, "message": "invalid signature"}

    try:
        data = await request.json()
    except Exception:
        return {"success": False, "message": "invalid json"}

    invoice_id = data.get("invoice_id")
    status = str(data.get("status", "")).strip().lower()

    if not invoice_id:
        return {"success": False, "message": "missing invoice"}

    logging.info(
        "BayarGG webhook | invoice=%s | status=%s",
        invoice_id,
        status
    )

    if status != "paid":
        return {"success": True, "message": "ignored"}

    redis_key = f"webhook:bayargg:{invoice_id}"

    try:
        locked = await redis_client.set(
            redis_key,
            "1",
            ex=86400,
            nx=True
        )

        if not locked:
            return {
                "success": True,
                "message": "already processed"
            }

    except Exception:
        logging.exception("Redis lock failed")

    pool = await get_pool()

    # =========================
    # CEK VIP PAYMENT
    # =========================

    vip_tx = await pool.fetchrow(
        """
        SELECT *
        FROM payments
        WHERE invoice_id=$1
        """,
        invoice_id
    )

    if vip_tx:

        if vip_tx["status"] == "paid":
            return {
                "success": True,
                "message": "vip already processed"
            }

        await pool.execute(
            """
            UPDATE payments
            SET
                status='paid',
                updated_at=NOW()
            WHERE invoice_id=$1
              AND status!='paid'
            """,
            invoice_id
        )

        paket = vip_tx["code"]

        vip_days = {
            "vip1": 1,
            "vip3": 3,
            "vip5": 5,
            "vip7": 7,
            "vip10": 10,
            "vip20": 20,
            "vip30": 30
        }

        days = vip_days.get(paket, 30)

        await pool.execute(
            """
            UPDATE users
            SET
                vip=TRUE,
                vip_until=
                CASE
                    WHEN vip_until IS NULL
                         OR vip_until < NOW()
                    THEN NOW() + ($2 || ' days')::interval
                    ELSE vip_until + ($2 || ' days')::interval
                END
            WHERE telegram_id=$1
            """,
            vip_tx["user_id"],
            days
        )

        try:
            await bot.send_message(
                vip_tx["user_id"],
                (
                    "💎 <b>VIP BERHASIL DIAKTIFKAN</b>\n\n"
                    f"Durasi : {days} hari"
                ),
                parse_mode="HTML"
            )
        except Exception:
            logging.exception("vip notify failed")

        try:
            await bot.send_message(
                ADMIN_CHAT_ID,
                (
                    "💎 <b>VIP PURCHASE</b>\n\n"
                    f"👤 User : <code>{vip_tx['user_id']}</code>\n"
                    f"📦 Paket : <code>{paket}</code>\n"
                    f"🧾 Invoice : <code>{invoice_id}</code>\n"
                    f"💰 Amount : Rp {vip_tx['amount']:,}"
                ).replace(",", "."),
                parse_mode="HTML"
            )
        except Exception:
            logging.exception("vip admin notify failed")

        return {
            "success": True,
            "message": "vip activated"
        }

    # =========================
    # CEK FILE PAYMENT
    # =========================

    file_tx = await pool.fetchrow(
        """
        SELECT
            user_id,
            owner_id,
            paid_price,
            file_code,
            status
        FROM file_purchases
        WHERE payment_id=$1
        """,
        invoice_id
    )

    if not file_tx:
        logging.warning(
            "Invoice %s tidak ditemukan",
            invoice_id
        )

        return {
            "success": False,
            "message": "transaction not found"
        }

    if file_tx["status"] == "paid":
        return {
            "success": True,
            "message": "already paid"
        }

    updated = await pool.execute(
        """
        UPDATE file_purchases
        SET
            status='paid',
            paid_at=NOW()
        WHERE payment_id=$1
          AND status='pending'
        """,
        invoice_id
    )

    if updated == "UPDATE 0":
        return {
            "success": True,
            "message": "already processed"
        }

    try:
        await pool.execute(
            """
            UPDATE users
            SET balance = balance + $1
            WHERE telegram_id = $2
            """,
            file_tx["paid_price"],
            file_tx["owner_id"]
        )
    except Exception:
        logging.exception("failed update owner balance")

    try:
        await bot.send_message(
            file_tx["user_id"],
            "✅ <b>Pembayaran Berhasil!</b>\n\nFile kamu sudah aktif.",
            parse_mode="HTML"
        )
    except Exception:
        logging.exception("user notify failed")

    try:
        await bot.send_message(
            ADMIN_CHAT_ID,
            (
                "💰 <b>PAYMENT SUCCESS</b>\n\n"
                f"🧾 Invoice : <code>{invoice_id}</code>\n"
                f"👤 User : <code>{file_tx['user_id']}</code>\n"
                f"📂 File : <code>{file_tx['file_code']}</code>\n"
                f"💵 Amount : Rp {file_tx['paid_price']:,}"
            ).replace(",", "."),
            parse_mode="HTML"
        )
    except Exception:
        logging.exception("admin notify failed")

    logging.info(
        "Invoice %s processed successfully",
        invoice_id
    )

    return {
        "success": True
    }
