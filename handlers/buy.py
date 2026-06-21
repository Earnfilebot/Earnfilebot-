import asyncio
import logging

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
from handlers.start import render_home_fast

router = Router()


# =========================
# BUY HANDLER
# =========================
@router.callback_query(F.data.startswith("buy:"))
async def buy_handler(call: CallbackQuery):

    await call.answer()

    code = call.data.split(":")[1]
    user_id = call.from_user.id

    try:
        msg = await call.message.edit_text("⏳ Memproses pembayaran...")
    except Exception as e:
        logging.warning(f"EDIT FAIL: {e}")
        msg = call.message

    # =========================
    # DB SAFE
    # =========================
    try:
        pool = await get_pool()

        file = await pool.fetchrow(
            "SELECT * FROM files WHERE code=$1",
            code
        )

    except Exception as e:
        logging.exception(f"DB ERROR: {e}")
        return await msg.edit_text("❌ Database error")

    if not file:
        return await msg.edit_text("❌ File tidak ditemukan")

    amount = file["price"] or 0

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

        return await msg.edit_text(
            "🆓 FILE GRATIS",
            reply_markup=kb
        )

    # =========================
    # INVOICE
    # =========================
    try:
        res = await create_invoice(amount, code, user_id)
    except Exception as e:
        logging.exception(f"INVOICE ERROR: {e}")
        return await msg.edit_text("❌ Gagal membuat invoice")

    if not res:
        return await msg.edit_text("❌ Invoice kosong")

    qris = res.get("qris_string")

    if not qris:
        return await msg.edit_text("❌ QRIS tidak tersedia")

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
        "📲 Scan QR untuk bayar"
    )

    # =========================
    # QR GENERATE SAFE
    # =========================
    try:
        await msg.edit_text("⏳ Membuat QRIS...")

        qr_img = generate_qr_image(qris)

        if not qr_img:
            return await msg.edit_text("❌ QR gagal dibuat")

        photo = BufferedInputFile(
            qr_img.getvalue(),
            filename="qris.png"
        )

        await msg.delete()

        await call.message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=kb
        )

    except Exception as e:
        logging.exception(f"QR ERROR: {e}")
        try:
            await msg.edit_text("⚠️ Gagal membuat QRIS")
        except:
            pass


# =========================
# CANCEL
# =========================
@router.callback_query(F.data == "cancel")
async def cancel_handler(call: CallbackQuery):

    await call.answer("❌ Pembayaran dibatalkan", show_alert=True)

    try:
        await render_home_fast(
            call.bot,
            call.message,
            call.from_user.id
        )
    except Exception as e:
        logging.exception(f"CANCEL ERROR: {e}")
