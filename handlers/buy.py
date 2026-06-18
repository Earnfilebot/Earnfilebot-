import asyncio
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


# =========================
# BUY HANDLER
# =========================
@router.callback_query(F.data.startswith("buy:"))
async def buy_handler(call: CallbackQuery):

    await call.answer()

    code = call.data.split(":")[1]
    user_id = call.from_user.id

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
    except:
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
                        callback_data="home"
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
    res = await create_invoice(amount, code, user_id)

    if not res:
        return await loading.edit_text("❌ Gagal membuat invoice")

    qris = res.get("qris_string")

    if not qris:
        return await loading.edit_text("❌ QRIS tidak tersedia")

    # =========================
    # BUTTON
    # =========================
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ BATAL",
                    callback_data="cancel"
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
    # QRIS GENERATE (FIXED)
    # =========================
    try:
        await loading.edit_text("⏳ Membuat QRIS...")

        qr_img = generate_qr_image(qris)

        if not qr_img:
            return await loading.edit_text("❌ Gagal generate QR")

        photo = BufferedInputFile(
            qr_img.getvalue(),
            filename="qris.png"
        )

        await loading.delete()

        await call.message.answer_photo(
            photo=photo,
            caption=caption + "📲 Scan QR untuk bayar",
            reply_markup=kb
        )

    except Exception as e:
        print("QR ERROR:", repr(e))
        await loading.edit_text("⚠️ Gagal membuat QRIS")


# =========================
# CANCEL HANDLER
# =========================
from handlers.start import render_home_fast

@router.callback_query(F.data == "cancel")
async def cancel_handler(call: CallbackQuery):
    await call.answer("❌ Pembayaran dibatalkan", show_alert=True)

    await render_home_fast(
        call.bot,
        call.message,
        call.from_user.id
    )
