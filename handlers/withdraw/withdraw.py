import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from database import get_pool

from handlers.withdraw.utils import (
    withdraw_is_open,
    rupiah,
    MIN_WITHDRAW,
    WITHDRAW_FEE,
    WITHDRAW_NOMINALS,
    INSTANT_AMOUNT,
    INSTANT_FEE,
    INSTANT_MIN_BALANCE,
)


router = Router()

logger = logging.getLogger(__name__)


# =========================
# MENU WITHDRAW
# =========================

@router.callback_query(F.data == "withdraw")
async def withdraw_menu(call: CallbackQuery):

    await call.answer()

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🏦 Rekening / E-Wallet",
        callback_data="withdraw_account"
    )

    if withdraw_is_open():

        status = "🟢 <b>BUKA</b>"

        kb.button(
            text="💸 Withdraw Reguler",
            callback_data="withdraw_create"
        )

        kb.button(
            text="⚡ Withdraw Instant",
            callback_data="withdraw_instant"
        )

    else:

        status = "🔴 <b>TUTUP</b>"

        kb.button(
            text="🔒 Withdraw Tutup",
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


    text = (
        "💸 <b>WITHDRAW SALDO</b>\n"
        "━━━━━━━━━━━━━━\n\n"

        f"📌 Status : {status}\n\n"

        "🕘 <b>Jam Operasional</b>\n"
        "• Senin - Jumat\n"
        "• 09:00 - 19:00 WIB\n"
        "• Sabtu & Minggu Libur\n\n"

        "💸 <b>Withdraw Reguler</b>\n"
        f"• Minimal : {rupiah(MIN_WITHDRAW)}\n"
        f"• Fee Admin : {rupiah(WITHDRAW_FEE)}\n\n"

        "⚡ <b>Withdraw Instant</b>\n"
        f"• Nominal : {rupiah(INSTANT_AMOUNT)}\n"
        f"• Fee : {rupiah(INSTANT_FEE)}\n"
        f"• Minimal saldo : {rupiah(INSTANT_MIN_BALANCE)}"
    )


    try:

        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

    except TelegramBadRequest as e:

        if "message is not modified" not in str(e).lower():
            logger.exception(e)



# =========================
# CREATE REGULER
# =========================

@router.callback_query(F.data == "withdraw_create")
async def withdraw_create(call: CallbackQuery):

    await call.answer()


    if not withdraw_is_open():

        return await call.answer(
            "Withdraw sedang tutup.",
            show_alert=True
        )


    pool = await get_pool()


    account = await pool.fetchrow(
        """
        SELECT
            uwa.id,
            uwa.account_name,
            uwa.account_number,
            wm.name AS method_name
        FROM user_withdraw_accounts uwa

        JOIN withdraw_methods wm
        ON wm.id = uwa.method_id

        WHERE uwa.user_id=$1
        AND uwa.is_default=true

        LIMIT 1
        """,
        call.from_user.id
    )


    if not account:

        kb = InlineKeyboardBuilder()

        kb.button(
            text="➕ Tambah Rekening",
            callback_data="withdraw_account"
        )

        kb.button(
            text="🔙 Kembali",
            callback_data="withdraw"
        )

        kb.adjust(1)


        return await call.message.edit_text(
            (
                "❌ <b>Rekening belum ada</b>\n\n"
                "Tambahkan rekening / e-wallet terlebih dahulu."
            ),
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )


    balance = await pool.fetchval(
        """
        SELECT balance
        FROM users
        WHERE telegram_id=$1
        """,
        call.from_user.id
    ) or 0



    kb = InlineKeyboardBuilder()


    for amount in WITHDRAW_NOMINALS:

        kb.button(
            text=rupiah(amount),
            callback_data=f"wd_amount:{amount}"
        )


    kb.button(
        text="❌ Batal",
        callback_data="withdraw"
    )


    kb.adjust(2)


    await call.message.edit_text(

        (
            "💸 <b>WITHDRAW REGULER</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"💰 Saldo : <b>{rupiah(balance)}</b>\n\n"

            f"🏦 {account['method_name']}\n"
            f"👤 {account['account_name']}\n"
            f"💳 <code>{account['account_number']}</code>\n\n"

            f"💸 Fee : {rupiah(WITHDRAW_FEE)}\n\n"

            "👇 Pilih nominal withdraw"
        ),

        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )



# =========================
# PILIH NOMINAL
# =========================

@router.callback_query(F.data.startswith("wd_amount:"))
async def withdraw_amount(call: CallbackQuery):

    await call.answer()


    amount = int(
        call.data.split(":")[1]
    )


    if amount not in WITHDRAW_NOMINALS:

        return await call.answer(
            "Nominal tidak valid",
            show_alert=True
        )


    kb = InlineKeyboardBuilder()


    kb.button(
        text="✅ Lanjutkan",
        callback_data=f"withdraw_confirm:{amount}"
    )

    kb.button(
        text="❌ Batal",
        callback_data="withdraw"
    )

    kb.adjust(1)


    await call.message.edit_text(

        (
            "💸 <b>DETAIL WITHDRAW</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"💰 Nominal : <b>{rupiah(amount)}</b>\n"
            f"💸 Fee : <b>{rupiah(WITHDRAW_FEE)}</b>\n"
            f"📉 Total Potong : <b>{rupiah(amount + WITHDRAW_FEE)}</b>\n\n"

            "Klik lanjutkan untuk membuat withdraw."
        ),

        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
