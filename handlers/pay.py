import qrcode
from io import BytesIO

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile
)

from database import get_pool
from utils.bayargg import BayarGG
from utils.redis_client import safe_set, safe_delete

router = Router()

PAY_LOCK_TTL = 10
INVOICE_TTL = 3600


@router.callback_query(F.data.startswith("pay:"))
async def pay_file(call: CallbackQuery):
    user_id = call.from_user.id
    code = call.data.split(":")[1]

    lock_key = f"paylock:{user_id}:{code}"

    # =========================
    # REDIS LOCK (SAFE MODE)
    # =========================
    try:
        lock_ok = await safe_set(
            lock_key,
            "1",
            ex=PAY_LOCK_TTL,
            nx=True
        )
    except Exception:
        lock_ok = True

    if not lock_ok:
        return await call.answer(
            "⏳ Tunggu sebentar...",
            show_alert=True
        )

    pool = await get_pool()

    try:
        # =========================
        # GET FILE
        # =========================
        file = await pool.fetchrow(
            """
            SELECT owner_id, price, is_paid
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
        # CHECK EXISTING TX
        # =========================
        existing = await pool.fetchrow(
            """
            SELECT payment_id, status
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
                return await call.answer(
                    "⏳ Invoice masih aktif",
                    show_alert=True
                )

        # =========================
        # CREATE PAYMENT
        # =========================
        data = await BayarGG.create_payment(
            amount=price,
            description=f"File {code}",
            customer_name=call.from_user.full_name
        )

        invoice_id = data.get("invoice_id")
        qr_string = data.get("qris_string")

        print("SAVE PAYMENT ID:", invoice_id)

        if not invoice_id or not qr_string:
            return await call.answer(
                "Payment error",
                show_alert=True
            )

        # =========================
        # SAVE DB
        # =========================
        await pool.execute(
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
            VALUES (
                $1,$2,$3,$4,$5,
                'pending',
                NOW()
            )
            ON CONFLICT (payment_id)
            DO UPDATE
            SET status='pending'
            """,
            user_id,
            code,
            file["owner_id"],
            price,
            invoice_id
        )

        # =========================
        # REDIS INVOICE TRACK
        # =========================
        try:
            await safe_set(
                f"invoice:{invoice_id}",
                f"{user_id}:{code}:pending",
                ex=INVOICE_TTL
            )
        except Exception:
            pass

        # =========================
        # GENERATE QR
        # =========================
        qr = qrcode.make(qr_string)

        buf = BytesIO()
        qr.save(buf, format="PNG")
        buf.seek(0)

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
        msg = await call.message.answer_photo(
            BufferedInputFile(
                buf.read(),
                filename="qris.png"
            ),
            caption=(
                "💳 <b>PAYMENT QRIS</b>\n\n"
                f"🧾 Invoice: <code>{invoice_id}</code>\n"
                f"💰 Rp {price:,}\n\n"
                "Scan untuk bayar"
            ).replace(",", "."),
            parse_mode="HTML",
            reply_markup=kb
        )

        # =========================
        # SAVE MESSAGE ID
        # =========================
        await pool.execute(
            """
            UPDATE file_purchases
            SET qr_message_id=$1,
                qr_chat_id=$2
            WHERE payment_id=$3
            """,
            msg.message_id,
            msg.chat.id,
            invoice_id
        )

        await call.answer()

    finally:
        try:
            await safe_delete(lock_key)
        except Exception:
            pass
