import qrcode
from io import BytesIO
import logging

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile
)

from database import fetchrow, execute
from utils.bayargg import BayarGG
from utils.redis_client import safe_set, safe_delete


logger = logging.getLogger(__name__)

router = Router()

PAY_LOCK_TTL = 30
INVOICE_TTL = 3600


@router.callback_query(F.data.startswith("pay:"))
async def pay_file(call: CallbackQuery):

    logger.info(
        "MASUK PAY FILE | %s",
        call.data
    )

    await call.answer("⏳ Memproses pembayaran...")

    user_id = call.from_user.id
    code = call.data.split(":")[1]

    loading = await call.message.answer(
        "⏳ <b>Membuat QRIS...</b>\n\nMohon tunggu sebentar.",
        parse_mode="HTML"
    )

    lock_key = f"paylock:{user_id}:{code}"


    # =========================
    # REDIS LOCK
    # =========================
    try:
        lock_ok = await safe_set(
            lock_key,
            "1",
            ex=PAY_LOCK_TTL,
            nx=True
        )

    except Exception:
        logger.exception("Redis lock error")
        lock_ok = True


    if not lock_ok:

        try:
            await loading.delete()
        except Exception:
            pass

        return await call.answer(
            "⏳ Tunggu sebentar...",
            show_alert=True
        )


    try:

        # =========================
        # GET FILE
        # =========================
        file = await fetchrow(
            """
            SELECT
                owner_id,
                price,
                is_paid
            FROM files
            WHERE code=$1
            """,
            code
        )


        if not file:
            return await call.answer(
                "❌ File tidak ditemukan",
                show_alert=True
            )


        if not file["is_paid"]:
            return await call.answer(
                "File gratis",
                show_alert=True
            )


        if file["owner_id"] == user_id:
            return await call.answer(
                "Owner tidak perlu bayar",
                show_alert=True
            )


        price = file["price"] or 0



        # =========================
        # CHECK EXISTING PAYMENT
        # =========================
        logger.info(
            "CHECK EXISTING PAYMENT | user=%s file=%s",
            user_id,
            code
        )
        existing = await fetchrow(
            """
            SELECT
                payment_id,
                status
            FROM file_purchases
            WHERE user_id=$1
              AND file_code=$2
            ORDER BY id DESC
            LIMIT 1
            """,
            user_id,
            code
        )


        if existing:

            if existing["status"] == "paid":
                return await call.answer(
                    "Sudah dibeli",
                    show_alert=True
                )


            if existing["status"] == "pending":
                logger.info(
                    "Old pending invoice ignored | %s",
                    existing["payment_id"]
                )

        # =========================
        # CREATE PAYMENT
        # =========================
        data = await BayarGG.create_payment(
            amount=price,
            description=f"File {code}",
            customer_name=call.from_user.full_name
        )
        final_amount = data.get("final_amount", price)


        logger.info(
            "BAYARGG RESPONSE | %s",
            data
        )


        if not data:

            return await call.answer(
                "❌ Gagal membuat pembayaran",
                show_alert=True
            )


        invoice_id = data.get("invoice_id")
        qr_string = data.get("qris_string")


        if not invoice_id or not qr_string:

            logger.error(
                "QR DATA INVALID | %s",
                data
            )

            return await call.answer(
                "❌ QRIS tidak tersedia",
                show_alert=True
            )


        logger.info(
            "PAYMENT CREATED | invoice=%s",
            invoice_id
        )



        # =========================
        # SAVE PAYMENT
        # =========================
        await execute(
            """
            INSERT INTO file_purchases
            (
                user_id,
                file_code,
                owner_id,
                paid_price,
                payment_id,
                status,
                created_at
            )
            VALUES
            (
                $1,$2,$3,$4,$5,
                'pending',
                NOW()
            )
            """,
            user_id,
            code,
            file["owner_id"],
            price,
            invoice_id
        )



        # =========================
        # REDIS TRACK
        # =========================
        try:

            await safe_set(
                f"invoice:{invoice_id}",
                f"{user_id}:{code}:pending",
                ex=INVOICE_TTL
            )

        except Exception:

            logger.exception(
                "Invoice redis failed"
            )



        # =========================
        # GENERATE QR
        # =========================
        qr = qrcode.make(
            qr_string
        )

        buf = BytesIO()

        qr.save(
            buf,
            format="PNG"
        )

        buf.seek(0)


        if buf.getbuffer().nbytes == 0:

            return await call.answer(
                "❌ QR gagal dibuat",
                show_alert=True
            )



        kb = InlineKeyboardMarkup(
            inline_keyboard=[

                [
                    InlineKeyboardButton(
                        text="✅ Check Payment",
                        callback_data=f"check:{invoice_id}"
                    )
                ],

                [
                    InlineKeyboardButton(
                        text="❌ Cancel",
                        callback_data=f"cancel:{invoice_id}"
                    )
                ]

            ]
        )


        # =========================
        # SEND QR
        # =========================
        logger.info(
            "TRY SEND QR | %s",
            invoice_id
        )

        # Hapus pesan "FILE BERBAYAR"
        try:

            await call.message.delete()

            logger.info(
                "PAY MESSAGE DELETED | user=%s file=%s",
                user_id,
                code
            )

        except Exception:

            logger.exception(
                "DELETE PAY MESSAGE ERROR"
            )


        msg = await call.message.answer_photo(
            BufferedInputFile(
                buf.getvalue(),
                filename="qris.png"
            ),

            caption=(
                "💳 <b>PAYMENT QRIS</b>\n\n"
                f"🧾 Invoice : <code>{invoice_id}</code>\n"
                f"💰 Total Bayar : Rp {final_amount:,}\n\n"
                "Scan QR untuk melakukan pembayaran."
            ).replace(",", "."),

            parse_mode="HTML",
            reply_markup=kb
        )



        # =========================
        # SAVE QR MESSAGE
        # =========================
        await execute(
            """
            UPDATE file_purchases
            SET
                qr_message_id=$1,
                qr_chat_id=$2
            WHERE payment_id=$3
            """,
            msg.message_id,
            msg.chat.id,
            invoice_id
        )


        logger.info(
            "QR SENT | invoice=%s | message=%s",
            invoice_id,
            msg.message_id
        )


    except Exception:

        logger.exception(
            "PAY FILE ERROR | user=%s | file=%s",
            user_id,
            code
        )

        raise



    finally:

        try:
            await loading.delete()

        except Exception:
            pass


        try:
            await safe_delete(
                lock_key
            )

        except Exception:
            pass
