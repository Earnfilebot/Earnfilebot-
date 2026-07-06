from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from database import get_pool
from utils.bayargg import BayarGG

import json

router = Router()

CHANNEL_ID = -1004395938795

status_map = {
    "pending": "⏳ Menunggu pembayaran",
    "paid": "✅ Sudah dibayar",
    "expired": "❌ Kadaluarsa"
}


@router.callback_query(F.data.startswith("check:"))
async def check_payment(call: CallbackQuery):
    invoice_id = call.data.split(":")[1]
    pool = await get_pool()

    # =========================
    # CEK PAYMENT GATEWAY
    # =========================
    try:
        data = await BayarGG.check_payment(invoice_id)
        print("CHECK PAYMENT:", data)

    except Exception as e:
        print("CHECK ERROR:", e)
        return await call.answer(
            "❌ Error gateway",
            show_alert=True
        )

    if not data:
        return await call.answer(
            "❌ Gagal cek payment",
            show_alert=True
        )

    status = str(data.get("status", "")).lower()

    # =========================
    # AMBIL TRANSAKSI
    # =========================
    tx = await pool.fetchrow(
        """
        SELECT
            user_id,
            file_code,
            status,
            qr_message_id,
            qr_chat_id
        FROM file_purchases
        WHERE payment_id=$1
        """,
        invoice_id
    )

    if not tx:
        return await call.answer(
            "Invoice tidak ditemukan",
            show_alert=True
        )

    # =========================
    # SUDAH DIPROSES
    # =========================
    if tx["status"] == "paid":
        return await call.answer(
            "✅ Sudah diproses",
            show_alert=True
        )

    # =========================
    # BELUM BAYAR
    # =========================
    if status != "paid":
        return await call.answer(
            status_map.get(status, "⏳ Menunggu pembayaran"),
            show_alert=True
        )

    # =========================
    # UPDATE DATABASE
    # =========================
    await pool.execute(
        """
        UPDATE file_purchases
        SET status='paid',
            paid_at=NOW()
        WHERE payment_id=$1
        """,
        invoice_id
    )

    # =========================
    # HAPUS PESAN QR
    # =========================
    try:
        if tx["qr_message_id"] and tx["qr_chat_id"]:
            await call.bot.delete_message(
                tx["qr_chat_id"],
                tx["qr_message_id"]
            )
    except Exception as e:
        print("DELETE QR ERROR:", e)

    # =========================
    # POST KE CHANNEL
    # =========================
    try:
        await call.bot.send_message(
            CHANNEL_ID,
            (
                "💰 <b>PAYMENT SUCCESS</b>\n\n"
                f"👤 User : <code>{tx['user_id']}</code>\n"
                f"📂 File : <code>{tx['file_code']}</code>\n"
                f"🧾 Invoice : <code>{invoice_id}</code>"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        print("CHANNEL POST ERROR:", e)

    # =========================
    # AMBIL FILE
    # =========================
    file = await pool.fetchrow(
        """
        SELECT media
        FROM files
        WHERE code=$1
        """,
        tx["file_code"]
    )

    if not file:
        return await call.answer(
            "File tidak ditemukan",
            show_alert=True
        )

    media = file["media"]

    if isinstance(media, str):
        media = json.loads(media)

    if not media:
        return await call.answer(
            "File rusak",
            show_alert=True
        )

    first = media[0]

    file_id = first.get("file_id")
    file_type = (first.get("type") or "document").lower()

    if not file_id:
        return await call.answer(
            "File invalid",
            show_alert=True
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📂 OPEN FILE",
                    callback_data=f"page:{tx['file_code']}:1"
                )
            ]
        ]
    )

    caption = (
        "✅ <b>PAYMENT BERHASIL</b>\n\n"
        f"🔑 CODE : <code>{tx['file_code']}</code>\n"
        f"📦 TOTAL FILE : {len(media)}\n\n"
        "Klik tombol di bawah untuk membuka semua file."
    )

    # =========================
    # KIRIM FILE KE USER
    # =========================
    try:
        if file_type == "photo":
            await call.bot.send_photo(
                tx["user_id"],
                file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )

        elif file_type == "video":
            await call.bot.send_video(
                tx["user_id"],
                file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )

        else:
            await call.bot.send_document(
                tx["user_id"],
                file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )

    except Exception as e:
        print("SEND FILE ERROR:", e)
        return await call.answer(
            "❌ Gagal kirim file",
            show_alert=True
        )

    await call.answer(
        "✅ Payment sukses & file dikirim",
        show_alert=True
    )
