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
# CHECK PAYMENT
# =========================
@router.callback_query(F.data.startswith("check_payment:"))
async def check_payment(call: CallbackQuery):

    code = call.data.split(":")[1]
    user_id = call.from_user.id

    await call.answer("🔍 Mengecek pembayaran...")

    try:
        pool = await get_pool()

        payment = await pool.fetchrow("""
            SELECT status
            FROM payments
            WHERE user_id=$1 AND code=$2
        """, user_id, code)

        if not payment:
            return await call.answer(
                "❌ Payment tidak ditemukan",
                show_alert=True
            )

        status = payment["status"]

        if status == "pending":
            return await call.answer(
                "⏳ Menunggu pembayaran",
                show_alert=True
            )

        if status != "paid":
            return await call.answer(
                f"❌ Status: {status}",
                show_alert=True
            )

        # =========================
        # PAYMENT SUCCESS
        # =========================
        file = await pool.fetchrow("""
            SELECT media_json
            FROM files
            WHERE code=$1
        """, code)

        if not file:
            return await call.answer(
                "❌ File tidak ditemukan",
                show_alert=True
            )

        try:
            media_list = json.loads(file["media_json"] or "[]")
        except Exception:
            media_list = []

        if not media_list:
            return await call.answer(
                "❌ File kosong",
                show_alert=True
            )

        try:
            await call.message.delete()
        except:
            pass

        await call.message.answer(
            "✅ PEMBAYARAN BERHASIL\n\n📂 Mengirim file..."
        )

        sent = 0

        for item in media_list:

            try:
                file_type = item.get("type")
                file_id = item.get("file_id")

                if not file_id:
                    continue

                if file_type == "video":
                    await call.bot.send_video(
                        chat_id=user_id,
                        video=file_id
                    )

                elif file_type == "document":
                    await call.bot.send_document(
                        chat_id=user_id,
                        document=file_id
                    )

                else:
                    await call.bot.send_photo(
                        chat_id=user_id,
                        photo=file_id
                    )

                sent += 1
                await asyncio.sleep(0.3)

            except Exception as e:
                logging.error(f"SEND FILE ERROR: {e}")

        await call.message.answer(
            f"✅ Selesai!\n\n📦 {sent} file berhasil dikirim"
        )

    except Exception as e:
        logging.exception(f"CHECK PAYMENT ERROR: {e}")

        await call.answer(
            "❌ SYSTEM ERROR",
            show_alert=True
        )


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
