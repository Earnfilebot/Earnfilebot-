from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

WIB = ZoneInfo("Asia/Jakarta")


def withdraw_is_open() -> bool:
    now = datetime.now(WIB)

    # Senin = 0 ... Minggu = 6
    if now.weekday() >= 5:
        return False

    return 9 <= now.hour < 19


@router.callback_query(F.data == "withdraw")
async def withdraw_menu(call: CallbackQuery):

    open_now = withdraw_is_open()

    kb = InlineKeyboardBuilder()

    # Rekening / E-Wallet
    kb.button(
        text="🏦 Rekening / E-Wallet",
        callback_data="withdraw_account"
    )

    if open_now:

        kb.button(
            text="🏦 Withdraw Reguler",
            callback_data="withdraw_create"
        )

        kb.button(
            text="⚡ Withdraw Instant",
            callback_data="withdraw_instant"
        )

    else:

        kb.button(
            text="🔒 Withdraw Sedang Tutup",
            callback_data="withdraw_closed"
        )

    kb.button(
        text="📜 Riwayat Withdraw",
        callback_data="withdraw_history"
    )

    kb.button(
        text="🔙 Kembali",
        callback_data="home"
    )

    kb.adjust(1)

    status = "🟢 BUKA" if open_now else "🔴 TUTUP"

    text = (
        "💸 <b>WITHDRAW SALDO</b>\n"
        "━━━━━━━━━━━━━━\n\n"

        f"📌 Status : <b>{status}</b>\n"
        "🕘 Jadwal Layanan\n"
        "• Senin - Jumat\n"
        "• 09:00 - 19:00 WIB\n"
        "• Sabtu & Minggu Tutup\n\n"

        "🏦 <b>Rekening / E-Wallet</b>\n"
        "Simpan rekening tujuan terlebih dahulu sebelum melakukan withdraw.\n\n"

        "💰 <b>Withdraw Reguler</b>\n"
        "• Minimal Rp 100.000\n"
        "• Fee Admin Rp 2.000\n"
        "• Diproses sesuai antrean admin\n\n"

        "⚡ <b>Withdraw Instant</b>\n"
        "• Minimal saldo Rp 60.000\n"
        "• Nominal withdraw Rp 50.000\n"
        "• Diproses lebih cepat\n"
        "• Prioritas di atas withdraw reguler"
    )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()
