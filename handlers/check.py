from aiogram import Router, F
from aiogram.types import CallbackQuery
import logging

from database import fetchrow
from utils.bayargg import BayarGG

logger = logging.getLogger(__name__)

router = Router()

status_map = {
    "pending": "⏳ Menunggu pembayaran",
    "expired": "❌ Kadaluarsa"
}


@router.callback_query(F.data.startswith("check:"))
async def check_payment(call: CallbackQuery):
    invoice_id = call.data.split(":")[1]

    try:
        logger.info(
            "Check payment | invoice=%s | user=%s",
            invoice_id,
            call.from_user.id
        )

        # =========================
        # CEK PAYMENT GATEWAY
        # =========================
        try:
            data = await BayarGG.check_payment(invoice_id)
        except Exception:
            return await call.answer(
                "❌ Error gateway",
                show_alert=True
            )

        if not data:
            logger.error(
                "Gateway returned empty response | invoice=%s",
                invoice_id
            )

            return await call.answer(
                "❌ Gagal cek payment",
                show_alert=True
            )

        status = str(data.get("status", "")).lower()

        # =========================
        # AMBIL TRANSAKSI DB
        # =========================
        tx = await fetchrow(
            """
            SELECT user_id, file_code, status
            FROM file_purchases
            WHERE payment_id=$1
            """,
            invoice_id
        )

        if not tx:
            logger.warning(
                "Invoice not found | invoice=%s",
                invoice_id
            )

            return await call.answer(
                "Invoice tidak ditemukan",
                show_alert=True
            )

        # =========================
        # SUDAH DIPROSES
        # =========================
        if tx["status"] == "paid":
            logger.info(
                "Invoice already processed | invoice=%s",
                invoice_id
            )

            return await call.answer(
                "✅ Sudah diproses oleh sistem",
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
        # SUDAH BAYAR TAPI BELUM DIPROSES WEBHOOK
        # =========================
        try:
            await call.message.delete()
        except Exception:
            pass

        logger.info(
            "Payment already paid, waiting webhook | invoice=%s",
            invoice_id
        )

        return await call.answer(
            "⏳ Pembayaran sudah diterima.\n"
            "Sedang diproses otomatis oleh server (webhook)...",
            show_alert=True
        )

    except Exception:
        logger.exception(
            "Check payment failed | invoice=%s | user=%s",
            invoice_id,
            call.from_user.id
        )
        raise
