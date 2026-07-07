from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from states.withdraw import WithdrawState
from aiogram.types import Message
from database import get_pool

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

# =========================
# TAMBAH REKENING
# =========================

@router.callback_query(F.data == "withdraw_add_account")
async def withdraw_add_account(call: CallbackQuery):

    pool = await get_pool()

    methods = await pool.fetch(
        """
        SELECT
            id,
            name
        FROM withdraw_methods
        WHERE enabled=TRUE
        ORDER BY id
        """
    )

    if not methods:

        return await call.answer(
            "Belum ada metode withdraw.",
            show_alert=True
        )

    kb = InlineKeyboardBuilder()

    for method in methods:

        kb.button(
            text=f"🏦 {method['name']}",
            callback_data=f"withdraw_method:{method['id']}"
        )

    kb.button(
        text="🔙 Kembali",
        callback_data="withdraw_account"
    )

    kb.adjust(1)

    await call.message.edit_text(
        (
            "🏦 <b>PILIH METODE WITHDRAW</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            "Silakan pilih Bank atau E-Wallet yang ingin disimpan."
        ),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()

# =========================
# PILIH METODE
# =========================

@router.callback_query(F.data.startswith("withdraw_method:"))
async def withdraw_method(
    call: CallbackQuery,
    state: FSMContext
):

    method_id = int(
        call.data.split(":")[1]
    )

    pool = await get_pool()

    method = await pool.fetchrow(
        """
        SELECT
            id,
            name
        FROM withdraw_methods
        WHERE id=$1
          AND enabled=TRUE
        """,
        method_id
    )

    if not method:

        return await call.answer(
            "Metode tidak ditemukan.",
            show_alert=True
        )

    await state.update_data(
        method_id=method["id"],
        method_name=method["name"]
    )

    await state.set_state(
        WithdrawState.input_account_number
    )

    await call.message.edit_text(
        (
            "🏦 <b>TAMBAH REKENING</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            f"Metode : <b>{method['name']}</b>\n\n"
            "Sekarang kirim nomor rekening atau "
            "nomor E-Wallet yang ingin disimpan."
        ),
        parse_mode="HTML"
    )

    await call.answer()

# =========================
# INPUT NOMOR REKENING
# =========================

@router.message(WithdrawState.input_account_number)
async def input_account_number(
    message: Message,
    state: FSMContext
):

    account_number = (
        message.text
        .strip()
        .replace(" ", "")
    )

    if (
        len(account_number) < 5
        or
        not account_number.isdigit()
    ):

        return await message.answer(
            "❌ Nomor rekening / E-Wallet tidak valid.\n\n"
            "Nomor hanya boleh berisi angka."
        )

    await state.update_data(
        account_number=account_number
    )

    await state.set_state(
        WithdrawState.input_account_name
    )

    await message.answer(
        (
            "👤 <b>NAMA PEMILIK</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            "Sekarang kirim nama lengkap pemilik rekening atau E-Wallet.\n\n"
            "Contoh:\n"
            "<code>abcde fghij</code>"
        ),
        parse_mode="HTML"
    )

# =========================
# INPUT NAMA PEMILIK
# =========================

@router.message(WithdrawState.input_account_name)
async def input_account_name(
    message: Message,
    state: FSMContext
):

    account_name = message.text.strip()

    if len(account_name) < 3:
        return await message.answer(
            "❌ Nama pemilik terlalu pendek.\n\n"
            "Silakan kirim kembali."
        )

    data = await state.get_data()

    pool = await get_pool()

    # =========================
    # CEK DUPLIKAT
    # =========================

    exists = await pool.fetchval(
        """
        SELECT 1
        FROM user_withdraw_accounts
        WHERE user_id=$1
          AND method_id=$2
          AND account_number=$3
        LIMIT 1
        """,
        message.from_user.id,
        data["method_id"],
        data["account_number"]
    )

    if exists:

        await state.clear()

        return await message.answer(
            "❌ Rekening atau E-Wallet tersebut sudah tersimpan."
        )

    # =========================
    # CEK REKENING PERTAMA
    # =========================

    total = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM user_withdraw_accounts
        WHERE user_id=$1
        """,
        message.from_user.id
    )

    is_default = total == 0

    # =========================
    # SIMPAN DATABASE
    # =========================

    await pool.execute(
        """
        INSERT INTO user_withdraw_accounts
        (
            user_id,
            method_id,
            account_name,
            account_number,
            is_default,
            updated_at
        )
        VALUES
        ($1,$2,$3,$4,$5,NOW())
        """,
        message.from_user.id,
        data["method_id"],
        account_name,
        data["account_number"],
        is_default
    )

    await state.clear()

    kb = InlineKeyboardBuilder()

    kb.button(
        text="📋 Daftar Rekening",
        callback_data="withdraw_accounts"
    )

    kb.button(
        text="➕ Tambah Lagi",
        callback_data="withdraw_add_account"
    )

    kb.button(
        text="🔙 Kembali",
        callback_data="withdraw_account"
    )

    kb.adjust(1)

    await message.answer(
        (
            "✅ <b>Rekening berhasil disimpan.</b>\n\n"
            f"🏦 Metode : <b>{data['method_name']}</b>\n"
            f"👤 Nama : <b>{account_name}</b>\n"
            f"💳 Nomor : <code>{data['account_number']}</code>\n\n"
            "Rekening ini sekarang bisa digunakan untuk withdraw."
        ),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
