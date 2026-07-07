from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from states.withdraw import WithdrawState
from database import get_pool

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

# =========================
# WITHDRAW REGULER
# =========================

@router.callback_query(F.data == "withdraw_create")
async def withdraw_create(
    call: CallbackQuery,
    state: FSMContext
):

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
        WHERE
            uwa.user_id=$1
            AND uwa.is_default=TRUE
        LIMIT 1
        """,
        call.from_user.id
    )

    if not account:

        kb = InlineKeyboardBuilder()

        kb.button(
            text="➕ Tambah Rekening",
            callback_data="withdraw_add_account"
        )

        kb.button(
            text="🔙 Kembali",
            callback_data="withdraw"
        )

        kb.adjust(1)

        await call.message.edit_text(
            (
                "❌ <b>Belum ada rekening default.</b>\n\n"
                "Silakan tambahkan rekening terlebih dahulu."
            ),
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

        return await call.answer()

    balance = await pool.fetchval(
        """
        SELECT balance
        FROM users
        WHERE telegram_id=$1
        """,
        call.from_user.id
    )

    await state.update_data(
        withdraw_account_id=account["id"]
    )

    await state.set_state(
        WithdrawState.input_withdraw_amount
    )

    await call.message.edit_text(
        (
            "💸 <b>WITHDRAW REGULER</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"💰 Saldo : <b>Rp {balance:,}</b>\n\n"

            "<b>Rekening Tujuan</b>\n"
            f"🏦 {account['method_name']}\n"
            f"👤 {account['account_name']}\n"
            f"💳 <code>{account['account_number']}</code>\n\n"

            "Minimal withdraw <b>Rp 100.000</b>\n"
            "Fee admin <b>Rp 2.000</b>\n\n"

            "Sekarang kirim nominal withdraw."
        ).replace(",", "."),
        parse_mode="HTML"
    )

    await call.answer()

# =========================
# INPUT NOMINAL WITHDRAW
# =========================

from aiogram.types import Message


@router.message(WithdrawState.input_withdraw_amount)
async def input_withdraw_amount(
    message: Message,
    state: FSMContext
):

    amount_text = (
        message.text
        .replace(".", "")
        .replace(",", "")
        .strip()
    )

    if not amount_text.isdigit():

        return await message.answer(
            "❌ Nominal tidak valid.\n\n"
            "Kirim hanya angka.\n"
            "Contoh: 100000"
        )


    amount = int(amount_text)


    if amount < 100000:

        return await message.answer(
            "❌ Minimal withdraw adalah Rp 100.000."
        )


    data = await state.get_data()


    pool = await get_pool()


    balance = await pool.fetchval(
        """
        SELECT balance
        FROM users
        WHERE telegram_id=$1
        """,
        message.from_user.id
    )


    if balance < amount:

        return await message.answer(
            (
                "❌ Saldo tidak mencukupi.\n\n"
                f"Saldo kamu: Rp {balance:,}"
            ).replace(",", ".")
        )


    fee = 2000

    total_cut = amount + fee


    if balance < total_cut:

        return await message.answer(
            (
                "❌ Saldo tidak cukup untuk fee admin.\n\n"
                f"Withdraw : Rp {amount:,}\n"
                f"Fee : Rp {fee:,}\n"
                f"Total : Rp {total_cut:,}"
            ).replace(",", ".")
        )


    await state.update_data(
        withdraw_amount=amount,
        withdraw_fee=fee
    )


    await state.set_state(
        WithdrawState.confirm_withdraw
    )


    kb = InlineKeyboardBuilder()

    kb.button(
        text="✅ Konfirmasi",
        callback_data="withdraw_confirm"
    )

    kb.button(
        text="❌ Batal",
        callback_data="withdraw_cancel"
    )

    kb.adjust(1)


    await message.answer(
        (
            "💸 <b>KONFIRMASI WITHDRAW</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"💰 Nominal : <b>Rp {amount:,}</b>\n"
            f"💸 Fee Admin : <b>Rp {fee:,}</b>\n"
            f"📉 Total Potong : <b>Rp {total_cut:,}</b>\n\n"

            "Pastikan data sudah benar."
        ).replace(",", "."),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
# =========================
# KONFIRMASI WITHDRAW
# =========================

@router.callback_query(F.data == "withdraw_confirm")
async def withdraw_confirm(
    call: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    if not data.get("withdraw_amount"):
        return await call.answer(
            "Data withdraw tidak ditemukan.",
            show_alert=True
        )


    pool = await get_pool()


    account = await pool.fetchrow(
        """
        SELECT
            uwa.account_name,
            uwa.account_number,
            wm.name AS method_name
        FROM user_withdraw_accounts uwa
        JOIN withdraw_methods wm
            ON wm.id = uwa.method_id
        WHERE uwa.id=$1
          AND uwa.user_id=$2
        """,
        data["withdraw_account_id"],
        call.from_user.id
    )


    if not account:

        await state.clear()

        return await call.answer(
            "Rekening tidak ditemukan.",
            show_alert=True
        )


    amount = data["withdraw_amount"]
    fee = data["withdraw_fee"]


    # cek saldo terakhir
    balance = await pool.fetchval(
        """
        SELECT balance
        FROM users
        WHERE telegram_id=$1
        """,
        call.from_user.id
    )


    if balance < amount + fee:

        await state.clear()

        return await call.answer(
            "Saldo tidak mencukupi.",
            show_alert=True
        )


    # =========================
    # POTONG SALDO
    # =========================

    await pool.execute(
        """
        UPDATE users
        SET balance = balance - $1
        WHERE telegram_id=$2
        """,
        amount + fee,
        call.from_user.id
    )


    # =========================
    # SIMPAN REQUEST WITHDRAW
    # =========================

    await pool.execute(
        """
        INSERT INTO withdrawals
        (
            user_id,
            account_id,
            amount,
            fee,
            status,
            created_at
        )
        VALUES
        ($1,$2,$3,$4,'pending',NOW())
        """,
        call.from_user.id,
        data["withdraw_account_id"],
        amount,
        fee
    )


    await state.clear()


    kb = InlineKeyboardBuilder()

    kb.button(
        text="📜 Riwayat Withdraw",
        callback_data="withdraw_history"
    )

    kb.button(
        text="🔙 Menu Withdraw",
        callback_data="withdraw"
    )

    kb.adjust(1)


    await call.message.edit_text(
        (
            "✅ <b>WITHDRAW BERHASIL DIBUAT</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"🏦 {account['method_name']}\n"
            f"👤 {account['account_name']}\n"
            f"💳 <code>{account['account_number']}</code>\n\n"

            f"💰 Nominal : <b>Rp {amount:,}</b>\n"
            f"💸 Fee : <b>Rp {fee:,}</b>\n\n"

            "⏳ Status : <b>MENUNGGU PROSES</b>\n\n"

            "Withdraw akan diproses oleh admin."
        ).replace(",", "."),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


    await call.answer()

# =========================
# BATAL WITHDRAW
# =========================

@router.callback_query(F.data == "withdraw_cancel")
async def withdraw_cancel(
    call: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await call.message.edit_text(
        (
            "❌ <b>Withdraw dibatalkan.</b>\n\n"
            "Kamu kembali ke menu withdraw."
        ),
        parse_mode="HTML"
    )

    await call.answer()
