import logging
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
    except:
        msg = call.message

    # =========================
    # GET FILE
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

    amount = int(file["price"] or 0)

    # =========================
    # FREE FILE
    # =========================
    if amount <= 0:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📂 OPEN FILE", callback_data=f"page:{code}:1")],
                [InlineKeyboardButton(text="🏠 HOME", callback_data="home")]
            ]
        )

        return await msg.edit_text("🆓 FILE GRATIS", reply_markup=kb)

    # =========================
    # CREATE INVOICE
    # =========================
    try:
        res = await create_invoice(amount, code, user_id)
    except Exception as e:
        logging.exception(f"INVOICE ERROR: {e}")
        return await msg.edit_text("❌ Gagal membuat invoice")

    if not res:
        return await msg.edit_text("❌ Invoice gagal")

    qris = res.get("qris_string")
    if not qris:
        return await msg.edit_text("❌ QRIS kosong")

    # =========================
    # KEYBOARD
    # =========================
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ BATAL", callback_data="cancel"),
                InlineKeyboardButton(text="✅ SUDAH BAYAR", callback_data=f"check_payment:{code}")
            ]
        ]
    )

    caption = (
        "💰 PEMBAYARAN FILE\n\n"
        f"📦 CODE: {code}\n"
        f"💵 PRICE: Rp {amount}\n\n"
        "📲 Scan QR untuk bayar"
    )

    # =========================
    # QR GENERATE
    # =========================
    try:
        await msg.edit_text("⏳ Membuat QRIS...")

        qr_img = generate_qr_image(qris)
        if not qr_img:
            return await msg.edit_text("❌ QR gagal dibuat")

        photo = BufferedInputFile(qr_img.getvalue(), filename="qris.png")

        await msg.delete()

        await call.message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=kb
        )

    except Exception as e:
        logging.exception(f"QR ERROR: {e}")
        try:
            await msg.edit_text("⚠️ QR error")
        except:
            pass


# =========================
# CHECK PAYMENT (FIXED)
# =========================
@router.callback_query(F.data.startswith("check_payment:"))
async def check_payment(call: CallbackQuery):

    await call.answer("🔍 Mengecek pembayaran...")

    code = call.data.split(":")[1]
    user_id = call.from_user.id

    pool = await get_pool()

    try:
        payment = await pool.fetchrow(
            "SELECT status FROM payments WHERE user_id=$1 AND code=$2",
            user_id, code
        )

        if not payment:
            return await call.answer("❌ Payment tidak ditemukan", show_alert=True)

        if payment["status"] != "paid":
            return await call.answer("⏳ Belum dibayar", show_alert=True)

        # =========================
        # GET FILE AFTER PAID
        # =========================
        file = await pool.fetchrow(
            "SELECT media_json FROM files WHERE code=$1",
            code
        )

        media_list = []
        try:
            import json
            media_list = json.loads(file["media_json"]) if file else []
        except:
            media_list = []

        await call.message.edit_text("✅ PAYMENT SUCCESS\n\n📂 Mengirim file...")

        sent = 0
        for item in media_list:
            try:
                t = item.get("type")
                fid = item.get("file_id")

                if t == "video":
                    await call.bot.send_video(user_id, fid)
                elif t == "document":
                    await call.bot.send_document(user_id, fid)
                else:
                    await call.bot.send_photo(user_id, fid)

                sent += 1
                await asyncio.sleep(0.3)

            except:
                continue

        await call.message.answer(f"✅ Selesai! {sent} file dikirim")

    except Exception as e:
        logging.exception(f"CHECK PAYMENT ERROR: {e}")
        await call.answer("❌ SYSTEM ERROR", show_alert=True)


# =========================
# CANCEL
# =========================
@router.callback_query(F.data == "cancel")
async def cancel_handler(call: CallbackQuery):

    await call.answer("❌ Dibatalkan", show_alert=True)

    try:
        await render_home_fast(
            call.bot,
            call.message,
            call.from_user.id
        )
    except Exception as e:
        logging.exception(f"CANCEL ERROR: {e}")
