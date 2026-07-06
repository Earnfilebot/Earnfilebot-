from aiogram import Router, F
from aiogram.types import CallbackQuery

from database import get_pool
from utils.redis_client import safe_delete

router = Router()


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_payment(call: CallbackQuery):
    invoice_id = call.data.split(":")[1]

    pool = await get_pool()

    tx = await pool.fetchrow(
        """
        SELECT status
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

    if tx["status"] == "paid":
        return await call.answer(
            "Invoice sudah dibayar",
            show_alert=True
        )

    await pool.execute(
        """
        UPDATE file_purchases
        SET status='expired'
        WHERE payment_id=$1
        """,
        invoice_id
    )

    try:
        await safe_delete(f"invoice:{invoice_id}")
    except Exception:
        pass

    # Hapus pesan QR beserta tombolnya
    try:
        await call.message.delete()
    except Exception:
        pass

    # Kirim pemberitahuan baru
    await call.message.answer(
        "❌ Invoice berhasil dibatalkan."
    )

    await call.answer(
        "Invoice dibatalkan",
        show_alert=True
    )
