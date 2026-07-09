import hmac
import hashlib
import logging

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from bot import bot
from config import (
    BAYARGG_WEBHOOK_SECRET,
    CHANNEL_ID
)
from config_vip import VIP_PACKAGES
from database import get_pool
from utils.redis_client import redis_client
from handlers.page import send_page


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/bayargg",
    tags=["BayarGG"]
)


def secure_compare(a: str, b: str):
    return hmac.compare_digest(
        a or "",
        b or ""
    )



@router.post("/webhook")
async def bayargg_webhook(request: Request):

    body = await request.body()

    signature = request.headers.get(
        "X-Webhook-Signature",
        ""
    )

    timestamp = request.headers.get(
        "X-Webhook-Timestamp",
        ""
    )

    try:

        data = await request.json()

    except Exception:

        logger.exception(
            "INVALID JSON"
        )

        return {
            "success": False
        }

    # ==========================
    # VERIFY SIGNATURE
    # ==========================

    signature_data = (
        f"{data['invoice_id']}|"
        f"{data['status']}|"
        f"{data['final_amount']}|"
        f"{timestamp}"
    )

    expected = hmac.new(
        BAYARGG_WEBHOOK_SECRET.encode(),
        signature_data.encode(),
        hashlib.sha256
    ).hexdigest()

    if not secure_compare(signature, expected):

        logger.warning("INVALID WEBHOOK SIGNATURE")
        logger.warning("RECEIVED SIGNATURE=%s", signature)
        logger.warning("EXPECTED SIGNATURE=%s", expected)
        logger.warning("SIGNATURE DATA=%s", signature_data)
        logger.warning("HEADER=%s", dict(request.headers))
        logger.warning("BODY=%s", body.decode(errors="ignore"))

        return {
            "success": False,
            "message": "Invalid signature"
        }

    invoice_id = data.get(
        "invoice_id"
    )

    status = (
        data.get("status")
        or ""
    ).lower()

    logger.info(
        "WEBHOOK | invoice=%s status=%s",
        invoice_id,
        status
    )

    if not invoice_id:

        return {
            "success": False
        }

    if status != "paid":

        return {
            "success": True
        }

    pool = await get_pool()



    # ===============================
    # CHECK DUPLICATE
    # ===============================

    lock_key = (
        f"payment_processing:{invoice_id}"
    )


    if await redis_client.get(lock_key):

        logger.info(
            "PROCESSING LOCK %s",
            invoice_id
        )

        return {
            "success":True
        }


    await redis_client.set(
        lock_key,
        "1",
        ex=300
    )



    try:


        # =================================
        # FILE PAYMENT
        # =================================

        purchase = await pool.fetchrow(
            """
            SELECT *
            FROM file_purchases
            WHERE payment_id=$1
            """,
            invoice_id
        )



        if purchase:


            file = await pool.fetchrow(
                """
                SELECT *
                FROM files
                WHERE code=$1
                """,
                purchase["file_code"]
            )



            if not file:

                logger.error(
                    "FILE NOT FOUND %s",
                    purchase["file_code"]
                )

                return {
                    "success":False
                }



            income = int(
                file["price"] * 0.9
            )



            # ==========================
            # DATABASE UPDATE
            # ==========================

            if purchase["status"] != "paid":


                async with pool.acquire() as conn:

                    async with conn.transaction():

                        await conn.execute(
                            """
                            UPDATE file_purchases
                            SET
                                status='paid',
                                paid_at=NOW()
                            WHERE payment_id=$1
                            """,
                            invoice_id
                        )


                        await conn.execute(
                            """
                            UPDATE users
                            SET
                                balance=balance+$1,
                                total_sales=total_sales+1,
                                total_income=total_income+$1
                            WHERE telegram_id=$2
                            """,
                            income,
                            file["owner_id"]
                        )



                logger.info(
                    "FILE PAYMENT SUCCESS %s",
                    invoice_id
                )



                # OWNER NOTIFY

                try:

                    await bot.send_message(
                        file["owner_id"],
                        (
                            "💰 <b>File Terjual</b>\n\n"
                            f"📂 File : {purchase['file_code']}\n"
                            f"💵 Masuk : Rp {income:,}"
                        ).replace(",", "."),
                        parse_mode="HTML"
                    )

                except Exception:

                    logger.exception(
                        "OWNER NOTIFY ERROR"
                    )




                # CHANNEL NOTIFY

                try:

                    await bot.send_message(
                        -1003894841696,
                        (
                            "✅ <b>SOLD OUT FILE</b>\n\n"
                            f"📂 File : <code>{purchase['file_code']}</code>\n"
                            f"👤 User : <code>{purchase['user_id']}</code>\n"
                            f"💰 Harga : Rp {file['price']:,}\n"
                        ).replace(",", "."),
                        parse_mode="HTML"
                    )

                except Exception:

                    logger.exception(
                        "CHANNEL NOTIFY ERROR"
                    )



            else:

                logger.info(
                    "FILE ALREADY PAID %s",
                    invoice_id
                )



            await redis_client.delete(
                f"invoice:{invoice_id}"
            )


            # ==========================
            # SEND OPEN FILE BUTTON
            # ==========================

            try:

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
                    (
                        "✅ <b>Pembayaran berhasil!</b>\n\n"
                        "━━━━━━━━━━━━━━\n\n"
                        "📦 <b>File sudah tersedia</b>\n\n"
                        "Klik tombol di bawah untuk membuka file.\n\n"
                        "━━━━━━━━━━━━━━"
                    ),
                    parse_mode="HTML",
                    reply_markup=kb
                )


                logger.info(
                    "OPEN FILE BUTTON SENT | user=%s file=%s",
                    purchase["user_id"],
                    purchase["file_code"]
                )


            except Exception:

                logger.exception(
                    "SEND OPEN FILE BUTTON ERROR"
                )


            return {
                "success": True
            }
        # =================================
        # VIP PAYMENT
        # =================================

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
                "success":False
            }



        paket = VIP_PACKAGES.get(
            trx["code"]
        )


        if not paket:

            return {
                "success":False
            }



        user = await pool.fetchrow(
            """
            SELECT vip_until
            FROM users
            WHERE telegram_id=$1
            """,
            trx["user_id"]
        )



        now = datetime.now(
            timezone.utc
        )



        if (
            user
            and user["vip_until"]
            and user["vip_until"] > now
        ):

            vip_until = (
                user["vip_until"]
                +
                timedelta(
                    days=paket["days"]
                )
            )

        else:

            vip_until = (
                now
                +
                timedelta(
                    days=paket["days"]
                )
            )



        async with pool.acquire() as conn:

            async with conn.transaction():

                await conn.execute(
                    """
                    UPDATE payments
                    SET status='paid'
                    WHERE invoice_id=$1
                    """,
                    invoice_id
                )


                await conn.execute(
                    """
                    UPDATE users
                    SET
                        vip=TRUE,
                        vip_started_at=NOW(),
                        vip_until=$1
                    WHERE telegram_id=$2
                    """,
                    vip_until,
                    trx["user_id"]
                )



        await bot.send_message(
            trx["user_id"],
            (
                "🎉 <b>VIP ACTIVE</b>\n\n"
                f"Paket : {paket['name']}\n"
                f"Expired : {vip_until:%d-%m-%Y %H:%M UTC}"
            ),
            parse_mode="HTML"
        )



        await bot.send_message(
            -1003894841696,
            (
                "💎 <b>VIP SOLD</b>\n\n"
                f"👤 User : <code>{trx['user_id']}</code>\n"
                f"📦 Paket : {paket['name']}"
            ),
            parse_mode="HTML"
        )



        return {
            "success":True
        }



    finally:


        await redis_client.delete(
            lock_key
        )
