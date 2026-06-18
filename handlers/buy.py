import json
import asyncio

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

    await call.answer()

    code = call.data.split(":")[1]
    user_id = call.from_user.id

    # =========================
    # ⏳ LOADING (NEW ADD)
    # =========================
    loading = await call.message.edit_text("⏳ Memproses pembayaran...")

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code=$1",
        code
    )

    if not file:
        return await loading.edit_text("❌ File tidak ditemukan")

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
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 HOME",
                        callback_data="home"   # 🔥 FIX BACK TO HOME
                    )
                ]
            ]
        )

        return await loading.edit_text(
            "🆓 FILE GRATIS",
            reply_markup=kb
        )

    # =========================
    # CREATE INVOICE
    # =========================
    res = await create_invoice(
        amount,
        code,
        user_id
    )

    if not res:
        return await loading.edit_text(
            "❌ Gagal membuat invoice"
        )

    qris = res.get("qris_string")
    pay_url = res.get("payment_url")

    if not qris and not pay_url:
        print("DEBUG RES:", res)

        return await loading.edit_text(
            "❌ Response BayarGG tidak valid"
        )

    # =========================
    # BUTTON (FIX BACK -> HOME)
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
                    text="🏠 HOME",
                    callback_data="home"   # 🔥 FIXED
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
    # QRIS (LOADING ADD BEFORE GENERATE)
    # =========================
    if qris:
        try:
            await loading.edit_text("⏳ Membuat QRIS...")

            qr_img = generate_qr_image(qris)

            if not qr_img:
                raise ValueError("QR image is None")

            photo = BufferedInputFile(
                qr_img.getvalue(),
                filename="qris.png"
            )

            await loading.delete()

            await call.message.answer_photo(
                photo=photo,
                caption=caption + "📲 Scan QRIS atau klik tombol",
                reply_markup=kb
            )

        except Exception as e:
            print("QR ERROR:", repr(e))

            await loading.edit_text(
                caption + "⚠️ Gagal membuat QRIS",
                reply_markup=kb
            )

    else:
        await loading.edit_text(
            caption + "🔗 QRIS tidak tersedia",
            reply_markup=kb
        )
