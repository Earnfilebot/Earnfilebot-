from utils.bayargg import BayarGG
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

router = Router()


@router.callback_query(F.data.startswith("pay:"))
async def pay_file(call: CallbackQuery):
    user_id = call.from_user.id
    code = call.data.split(":")[1]

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT owner_id, price, is_paid FROM files WHERE code=$1",
        code
    )

    if not file:
        return await call.answer("❌ File tidak ditemukan", show_alert=True)

    if not file["is_paid"]:
        return await call.answer("File gratis", show_alert=True)

    price = file["price"] or 0
    owner_id = file["owner_id"]

    # =========================
    # CHECK EXISTING PENDING
    # =========================
    existing = await pool.fetchrow(
        """
        SELECT payment_id, status
        FROM file_purchases
        WHERE user_id=$1 AND file_code=$2
        ORDER BY id DESC
        LIMIT 1
        """,
        user_id,
        code
    )

    if existing and existing["status"] == "pending":
        return await call.answer(
            "⏳ Kamu sudah punya invoice pending",
            show_alert=True
        )

    # =========================
    # CREATE PAYMENT
    # =========================
    try:
        invoice_id, qr_string = await create_payment_bayargg(
            price, code, call.from_user
        )
    except Exception as e:
        return await call.answer(f"Gagal payment: {e}", show_alert=True)

    # =========================
    # SAVE PENDING
    # =========================
    await pool.execute(
        """
        INSERT INTO file_purchases
        (user_id, file_code, owner_id, paid_price, payment_id, status)
        VALUES ($1,$2,$3,$4,$5,'pending')
        """,
        user_id,
        code,
        owner_id,
        price,
        invoice_id
    )

    # =========================
    # QR GENERATION
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
            ]
        ]
    )

    await call.message.answer_photo(
        BufferedInputFile(buf.read(), filename="qris.png"),
        caption=(
            "💳 <b>PAYMENT QRIS</b>\n\n"
            f"🧾 Invoice: {invoice_id}\n"
            f"💰 Rp {price:,}\n\n"
            "Scan & bayar sekarang"
        ).replace(",", "."),
        parse_mode="HTML",
        reply_markup=kb
    )

    await call.answer()
