from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import get_pool

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
