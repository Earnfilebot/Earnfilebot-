from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()


@router.callback_query(F.data == "withdraw_account")
async def withdraw_account(call: CallbackQuery):

    kb = InlineKeyboardBuilder()

    kb.button(
        text="➕ Tambah Rekening",
        callback_data="withdraw_add_account"
    )

    kb.button(
        text="📋 Daftar Rekening",
        callback_data="withdraw_accounts"
    )

    kb.button(
        text="🔙 Kembali",
        callback_data="withdraw"
    )

    kb.adjust(1)

    await call.message.edit_text(
        (
            "🏦 <b>REKENING / E-WALLET</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            "Simpan rekening atau e-wallet yang akan digunakan "
            "untuk menerima hasil withdraw.\n\n"
            "Kamu dapat menyimpan beberapa rekening sekaligus.\n\n"
            "Silakan pilih menu di bawah."
        ),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()
