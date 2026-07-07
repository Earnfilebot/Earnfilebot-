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
from config import BAYARGG_API_KEY, CHANNEL_ID
from config_vip import VIP_PACKAGES
from database import get_pool
from utils.redis_client import redis_client
from handlers.page import send_page


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/bayargg",
    tags=["BayarGG"]
)



def secure_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(
        a or "",
        b or ""
    )



@router.post("/webhook")
async def bayargg_webhook(request: Request):

    body = await request.body()

    signature = request.headers.get(
        "X-Callback-Signature",
        ""
    )


    expected = hmac.new(
        BAYARGG_API_KEY.encode(),
        body,
        hashlib.sha256
    ).hexdigest()



    # ==============================
    # SIGNATURE DEBUG
    # ==============================

    if not secure_compare(
        signature,
        expected
    ):

        logger.warning(
            "INVALID WEBHOOK SIGNATURE"
        )

        logger.warning(
            "HEADERS : %s",
            dict(request.headers)
        )

        logger.warning(
            "BODY : %s",
            body.decode(
                errors="ignore"
            )
        )

        # sementara lanjut
        # nanti setelah tahu format asli BayarGG dikunci kembali



    try:

        data = await request.json()

    except Exception:

        logger.exception(
            "JSON WEBHOOK ERROR"
        )

        return {
            "success":False
        }



    invoice_id = data.get(
        "invoice_id"
    )


    status = (
        data.get("status")
        or ""
    ).lower()



    logger.info(
        "WEBHOOK RECEIVED | invoice=%s status=%s",
        invoice_id,
        status
    )



    if not invoice_id:

        return {
            "success":False,
            "message":"missing invoice"
        }



    if status != "paid":

        return {
            "success":True,
            "message":"ignored"
        }



    # ==============================
    # DUPLICATE PROTECTION
    # ==============================

    webhook_key = (
        f"webhook:processed:{invoice_id}"
    )


    if await redis_client.get(
        webhook_key
    ):

        logger.info(
            "WEBHOOK ALREADY PROCESSED %s",
            invoice_id
        )

        return {
            "success":True
        }


    await redis_client.set(
        webhook_key,
        "1",
        ex=86400
    )



    pool = await get_pool()



    # =====================================================
    # FILE PAYMENT
    # =====================================================

    purchase = await pool.fetchrow(
        """
        SELECT *
        FROM file_purchases
        WHERE payment_id=$1
        """,
        invoice_id
    )



    if purchase:


        logger.info(
            "FILE PAYMENT FOUND | user=%s file=%s",
            purchase["user_id"],
            purchase["file_code"]
        )



        if purchase["status"] != "paid":

            await pool.execute(
                """
                UPDATE file_purchases
                SET
                    status='paid',
                    paid_at=NOW()
                WHERE payment_id=$1
                """,
                invoice_id
            )



            file = await pool.fetchrow(
                """
                SELECT
                    owner_id,
                    price
                FROM files
                WHERE code=$1
                """,
                purchase["file_code"]
            )



            if file:


                income = int(
                    file["price"] * 0.9
                )


                await pool.execute(
                    """
                    UPDATE users
                    SET
                        balance = balance + $1,
                        total_sales = total_sales + 1,
                        total_income = total_income + $1
                    WHERE telegram_id=$2
                    """,
                    income,
                    file["owner_id"]
                )


                try:

                    await bot.send_message(
                        file["owner_id"],
                        (
                            "💰 <b>File Terjual</b>\n\n"
                            f"📂 File : {purchase['file_code']}\n"
                            f"💵 Saldo : Rp {income:,}"
                        ).replace(",", "."),
                        parse_mode="HTML"
                    )

                except Exception:

                    logger.exception(
                        "OWNER NOTIFY FAILED"
                    )



        await redis_client.delete(
            f"invoice:{invoice_id}"
        )



        # ==============================
        # SEND FILE TO BUYER
        # ==============================

        user_id = purchase["user_id"]
        code = purchase["file_code"]



        try:

            await bot.send_message(
                user_id,
                "✅ <b>Pembayaran berhasil!</b>\n\n📦 Mengirim file...",
                parse_mode="HTML"
            )



            result = await send_page(
                bot=bot,
                chat_id=user_id,
                user_id=user_id,
                code=code,
                page=1
            )



            logger.info(
                "SEND PAGE RESULT | %s",
                result
            )



            if result:


                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📂 OPEN FILE",
                                callback_data=f"page:{code}:1"
                            )
                        ]
                    ]
                )


                await bot.send_message(
                    user_id,
                    "📦 File berhasil dikirim.",
                    reply_markup=kb
                )


            else:


                await bot.send_message(
                    user_id,
                    "❌ File gagal dikirim."
                )


        except Exception:

            logger.exception(
                "SEND FILE FAILED"
            )



        return {
            "success":True
        }





    # =====================================================
    # VIP PAYMENT
    # =====================================================


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
            "success":False,
            "message":"transaction not found"
        }



    if trx["status"] == "paid":

        return {
            "success":True
        }



    paket = VIP_PACKAGES.get(
        trx["code"]
    )


    if not paket:

        return {
            "success":False,
            "message":"invalid package"
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



    try:

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
            CHANNEL_ID,
            (
                "💎 VIP SOLD\n"
                f"User : {trx['user_id']}\n"
                f"Plan : {paket['name']}"
            )
        )


    except Exception:

        logger.exception(
            "VIP NOTIFY FAILED"
        )



    return {
        "success":True
    }
