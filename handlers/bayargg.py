import hmac
import hashlib
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request

from bot import bot
from config import BAYARGG_API_KEY, CHANNEL_ID
from config_vip import VIP_PACKAGES
from database import get_pool

router = APIRouter(prefix="/bayargg", tags=["BayarGG"])


# =========================
# SECURE COMPARE (ANTI TIMING ATTACK)
# =========================
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

    # =========================
    # VERIFY SIGNATURE (SECURE)
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

    pool = await get_pool()

    # =====================================================
    # ================= FILE PAYMENT =====================
    # =====================================================
    purchase = await pool.fetchrow(
        """
        SELECT *
        FROM file_purchases
        WHERE payment_id=$1
        FOR UPDATE
        """,
        invoice_id
    )

    if purchase:

        # =========================
        # IDEMPOTENCY GUARD
        # =========================
        if purchase["status"] == "paid":
            return {"success": True, "message": "already processed"}

        async with pool.acquire() as conn:
            async with conn.transaction():

                # MARK AS PAID FIRST (LOCK STEP)
                await conn.execute(
                    """
                    UPDATE file_purchases
                    SET status='paid',
                        paid_at=NOW()
                    WHERE payment_id=$1
                    """,
                    invoice_id
                )

                # OWNER UPDATE
                await conn.execute(
                    """
                    UPDATE users
                    SET
                        balance = balance + $1,
                        total_sales = total_sales + 1
                    WHERE telegram_id=$2
                    """,
                    purchase["paid_price"],
                    purchase["owner_id"]
                )

                # BUYER UPDATE
                await conn.execute(
                    """
                    UPDATE users
                    SET total_downloads = total_downloads + 1
                    WHERE telegram_id=$1
                    """,
                    purchase["user_id"]
                )

        # =========================
        # NOTIFICATION
        # =========================
        try:
            kb = {
                "inline_keyboard": [
                    [
                        {
                            "text": "📂 OPEN PAGE",
                            "callback_data": f"page:{purchase['file_code']}:1"
                        }
                    ]
                ]
            }

            await bot.send_message(
                purchase["user_id"],
                "✅ <b>Pembayaran Berhasil</b>\n\nFile sudah dibuka.",
                parse_mode="HTML",
                reply_markup=kb
            )

            await bot.send_message(
                CHANNEL_ID,
                (
                    "📁 <b>FILE PAID</b>\n\n"
                    f"👤 Buyer: <code>{purchase['user_id']}</code>\n"
                    f"👑 Owner: <code>{purchase['owner_id']}</code>\n"
                    f"🔑 Code: <code>{purchase['file_code']}</code>\n"
                    f"💰 Price: Rp {purchase['paid_price']:,}"
                ).replace(",", "."),
                parse_mode="HTML"
            )

        except Exception:
            logging.exception("file payment notify failed")

        return {"success": True}

    # =====================================================
    # ================= VIP PAYMENT =======================
    # =====================================================
    trx = await pool.fetchrow(
        """
        SELECT *
        FROM payments
        WHERE invoice_id=$1
        FOR UPDATE
        """,
        invoice_id
    )

    if not trx:
        return {"success": False, "message": "invoice not found"}

    if trx["status"] == "paid":
        return {"success": True, "message": "already processed"}

    paket = VIP_PACKAGES.get(trx["code"])

    if not paket:
        return {"success": False, "message": "invalid package"}

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

            await conn.execute(
                """
                UPDATE payments
                SET status='paid',
                    updated_at=NOW()
                WHERE invoice_id=$1
                """,
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

            await conn.execute(
                """
                INSERT INTO vip_users
                (user_id, plan, invoice_id, started_at, expires_at, active)
                VALUES ($1,$2,$3,NOW(),$4,TRUE)
                """,
                trx["user_id"],
                paket["name"],
                invoice_id,
                vip_until
            )

    try:
        await bot.send_message(
            trx["user_id"],
            (
                "🎉 <b>Pembayaran Berhasil</b>\n\n"
                f"💎 Paket: <b>{paket['name']}</b>\n"
                f"📅 Expired:\n<code>{vip_until}</code>"
            ),
            parse_mode="HTML"
        )

        await bot.send_message(
            CHANNEL_ID,
            (
                "💎 <b>VIP PURCHASED</b>\n\n"
                f"👤 User: <code>{trx['user_id']}</code>\n"
                f"📦 Paket: <b>{paket['name']}</b>\n"
                f"🧾 Invoice: <code>{invoice_id}</code>\n"
                f"📅 Expired: <code>{vip_until}</code>"
            ),
            parse_mode="HTML"
        )

    except Exception:
        logging.exception("vip notify failed")

    return {"success": True}
