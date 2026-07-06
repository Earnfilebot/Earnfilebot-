from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import get_pool
from utils.bayargg import BayarGG

router = Router()

status_map = {
    "pending": "⏳ Menunggu pembayaran",
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
    except Exception:
        return await call.answer("❌ Error gateway", show_alert=True)

    if not data:
        return await call.answer("❌ Gagal cek payment", show_alert=True)

    status = str(data.get("status", "")).lower()

    # =========================
    # AMBIL TRANSAKSI DB
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
    # SUDAH DIPROSES
    # =========================
    if tx["status"] == "paid":
        return await call.answer("✅ Sudah diproses oleh sistem", show_alert=True)

    # =========================
    # BELUM BAYAR
    # =========================
    if status != "paid":
        return await call.answer(
            status_map.get(status, "⏳ Menunggu pembayaran"),
            show_alert=True
        )

    # =========================
    # SUDAH BAYAR TAPI BELUM DIPROSES WEBHOOK
    # =========================
    return await call.answer(
        "⏳ Pembayaran sudah diterima.\n"
        "Sedang diproses otomatis oleh server (webhook)...",
        show_alert=True
    )
