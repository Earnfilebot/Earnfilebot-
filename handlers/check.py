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
    # 1. CEK GATEWAY (SAFE)
    # =========================
    try:
        data = await BayarGG.check_payment(invoice_id)
    except Exception as e:
        return await call.answer(f"❌ Error gateway", show_alert=True)

    if not data or "status" not in data:
        return await call.answer("❌ Gagal cek payment", show_alert=True)

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
        return await call.answer("Invoice tidak ditemukan", show_alert=True)

    # =========================
    # 3. SUDAH DIPROSES (ANTI DOUBLE)
    # =========================
    if tx["status"] == "paid":
        return await call.answer("✅ Sudah diproses", show_alert=True)

    # =========================
    # 4. BELUM BAYAR
    # =========================
    if data["status"] != "paid":
        return await call.answer(
            status_map.get(data["status"], data["status"]),
            show_alert=True
        )

    # =========================
    # 5. UPDATE STATUS
    # =========================
    await pool.execute(
        """
        UPDATE file_purchases
        SET status='paid'
        WHERE payment_id=$1
        """,
        invoice_id
    )

    # =========================
    # 6. AMBIL FILE
    # =========================
    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code=$1",
        tx["file_code"]
    )

    if not file:
        return await call.answer("File tidak ditemukan", show_alert=True)

    media = file["media"]
    if isinstance(media, str):
        media = json.loads(media)

    if not media:
        return await call.answer("File rusak", show_alert=True)

    first = media[0]

    if not first.get("file_id"):
        return await call.answer("File invalid", show_alert=True)

    # =========================
    # 7. KIRIM FILE
    # =========================
    try:
        await call.message.bot.send_document(
            tx["user_id"],
            first["file_id"],
            caption=f"📁 FILE: {tx['file_code']}\n✅ Payment berhasil"
        )
    except Exception:
        return await call.answer("❌ Gagal kirim file", show_alert=True)

    await call.answer("✅ Payment sukses & file dikirim", show_alert=True)
