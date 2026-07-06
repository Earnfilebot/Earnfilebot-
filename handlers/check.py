from aiogram import Router, F
from aiogram.types import CallbackQuery

from database import get_pool
from utils.bayargg import BayarGG

import json

router = Router()

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
    # 1. CEK GATEWAY
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
    # 2. AMBIL TRANSAKSI DB
    # =========================
    tx = await pool.fetchrow(
        """
        SELECT user_id, file_code, status
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
    # 3. SUDAH DIPROSES
    # =========================
    if tx["status"] == "paid":
        return await call.answer(
            "✅ Sudah diproses",
            show_alert=True
        )

    # =========================
    # 4. BELUM BAYAR
    # =========================
    if status != "paid":
        return await call.answer(
            status_map.get(status, "⏳ Menunggu pembayaran"),
            show_alert=True
        )

    # =========================
    # 5. UPDATE STATUS
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
    # 6. AMBIL FILE
    # =========================
    file = await pool.fetchrow(
        "SELECT media FROM files WHERE code=$1",
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

    # =========================
    # 7. KIRIM FILE
    # =========================
    try:
        if file_type == "photo":
            await call.message.bot.send_photo(
                tx["user_id"],
                file_id,
                caption=f"📁 FILE: {tx['file_code']}\n✅ Payment berhasil"
            )

        elif file_type == "video":
            await call.message.bot.send_video(
                tx["user_id"],
                file_id,
                caption=f"📁 FILE: {tx['file_code']}\n✅ Payment berhasil"
            )

        else:
            await call.message.bot.send_document(
                tx["user_id"],
                file_id,
                caption=f"📁 FILE: {tx['file_code']}\n✅ Payment berhasil"
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
