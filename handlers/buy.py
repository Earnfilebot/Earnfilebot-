import json

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile
)

from database import get_pool
from utils.qr import generate_qr_image
from utils.payment import create_invoice

router = Router()


@router.callback_query(F.data.startswith("buy:"))
async def buy_handler(call: CallbackQuery):

    # Jawab callback secepat mungkin
    await call.answer()

    code = call.data.split(":")[1]
    user_id = call.from_user.id

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code=$1",
        code
    )

    if not file:
        await call.message.answer("❌ File tidak ditemukan")
        return

    # =========================
    # SAFE PRICE
    # =========================
    try:
        amount = int(file.get("price") or 0)
    except Exception:
        amount = 0

    # =========================
    # FREE FILE
    # =========================
    if amount <= 0:
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

        await call.message.answer(
            "🆓 FILE GRATIS",
            reply_markup=kb
        )
        return

    # =========================
    # CREATE INVOICE
    # =========================
    res = await create_invoice(
        amount,
        code,
        user_id
    )

    if not res:
        await call.message.answer(
            "❌ Gagal membuat invoice"
        )
        return

    # =========================
    # EXTRACT DATA
    # =========================
    qris = res.get("qris_string")
    pay_url = res.get("payment_url")

    if not qris and not pay_url:
        print("DEBUG RES:", res)

        await call.message.answer(
            "❌ Response BayarGG tidak valid"
        )
        return

    # =========================
    # BUTTON
    # =========================
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 BAYAR SEKARANG",
                    url=pay_url or "https://www.bayar.gg"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ BACK",
                    callback_data=f"page:{code}:1"
                )
            ]
        ]
    )

    caption = (
        "💰 PEMBAYARAN FILE\n\n"
        "━━━━━━━━━━━━━━\n"
        f"📦 CODE: {code}\n"
        f"💵 PRICE: Rp {amount}\n\n"
    )

    # =========================
    # QRIS
    # =========================
    if qris:
        try:
            qr_img = generate_qr_image(qris)

            if not qr_img:
                raise ValueError("QR image is None")

            photo = BufferedInputFile(
                qr_img.getvalue(),
                filename="qris.png"
            )

            await call.message.answer_photo(
                photo=photo,
                caption=caption + "📲 Scan QRIS atau klik tombol",
                reply_markup=kb
            )

        except Exception as e:
            print("QR ERROR:", repr(e))

            await call.message.answer(
                caption + "⚠️ Gagal membuat QRIS",
                reply_markup=kb
            )

    else:
        await call.message.answer(
            caption + "🔗 QRIS tidak tersedia",
            reply_markup=kb
        )
