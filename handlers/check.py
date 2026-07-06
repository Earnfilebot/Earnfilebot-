from aiogram import Router, F
from aiogram.types import CallbackQuery

from database import get_pool
from utils.bayargg import BayarGG

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
    # 1. CEK KE GATEWAY
    # =========================
    data = await BayarGG.check_payment(invoice_id)

    if not data:
        return await call.answer("❌ Gagal cek payment", show_alert=True)

    # =========================
    # 2. UPDATE STATUS JIKA SUDAH BAYAR
    # =========================
    if data.get("status") == "paid":

        await pool.execute(
            """
            UPDATE file_purchases
            SET status='paid'
            WHERE payment_id=$1
            """,
            invoice_id
        )

        purchase = await pool.fetchrow(
            """
            SELECT user_id, file_code
            FROM file_purchases
            WHERE payment_id=$1
            """,
            invoice_id
        )

        if not purchase:
            return await call.answer("Data pembelian tidak ditemukan", show_alert=True)

        file = await pool.fetchrow(
            "SELECT * FROM files WHERE code=$1",
            purchase["file_code"]
        )

        if not file:
            return await call.answer("File tidak ditemukan", show_alert=True)

        media = json.loads(file["media"]) if isinstance(file["media"], str) else file["media"]
        first = media[0] if media else None

        if not first:
            return await call.answer("File rusak", show_alert=True)

        await call.message.bot.send_document(
            purchase["user_id"],
            first["file_id"],
            caption=f"📁 FILE: {purchase['file_code']}\n✅ Payment berhasil"
        )

        await call.answer("✅ Payment sukses & file dikirim", show_alert=True)
        return

    # =========================
    # 3. BELUM BAYAR
    # =========================
    tx = await pool.fetchrow(
        "SELECT status FROM file_purchases WHERE payment_id=$1",
        invoice_id
    )

    if not tx:
        return await call.answer("Invoice tidak ditemukan", show_alert=True)

    await call.answer(
        status_map.get(tx["status"], tx["status"]),
        show_alert=True
    )
