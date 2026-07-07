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

# =========================
# DAFTAR REKENING
# =========================

@router.callback_query(F.data == "withdraw_accounts")
async def withdraw_accounts(call: CallbackQuery):

    pool = await get_pool()

    accounts = await pool.fetch(
        """
        SELECT
            uwa.id,
            uwa.account_name,
            uwa.account_number,
            uwa.is_default,
            wm.name AS method_name
        FROM user_withdraw_accounts uwa
        JOIN withdraw_methods wm
            ON wm.id = uwa.method_id
        WHERE uwa.user_id=$1
        ORDER BY
            uwa.is_default DESC,
            uwa.id ASC
        """,
        call.from_user.id
    )

    if not accounts:

        kb = InlineKeyboardBuilder()

        kb.button(
            text="➕ Tambah Rekening",
            callback_data="withdraw_add_account"
        )

        kb.button(
            text="🔙 Kembali",
            callback_data="withdraw_account"
        )

        kb.adjust(1)

        await call.message.edit_text(
            (
                "📋 <b>DAFTAR REKENING</b>\n"
                "━━━━━━━━━━━━━━\n\n"
                "Kamu belum memiliki rekening yang tersimpan."
            ),
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

        return await call.answer()

    kb = InlineKeyboardBuilder()

    text = (
        "📋 <b>DAFTAR REKENING</b>\n"
        "━━━━━━━━━━━━━━\n\n"
    )

    for acc in accounts:

        status = " ⭐ Default" if acc["is_default"] else ""

        text += (
            f"🏦 <b>{acc['method_name']}</b>{status}\n"
            f"👤 {acc['account_name']}\n"
            f"💳 <code>{acc['account_number']}</code>\n\n"
        )

        kb.button(
            text=f"⚙️ {acc['method_name']} • {acc['account_number']}",
            callback_data=f"withdraw_account_detail:{acc['id']}"
        )

    kb.button(
        text="➕ Tambah Rekening",
        callback_data="withdraw_add_account"
    )

    kb.button(
        text="🔙 Kembali",
        callback_data="withdraw_account"
    )

    kb.adjust(1)

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()

# =========================
# DETAIL REKENING
# =========================

@router.callback_query(F.data.startswith("withdraw_account_detail:"))
async def withdraw_account_detail(call: CallbackQuery):

    account_id = int(call.data.split(":")[1])

    pool = await get_pool()

    account = await pool.fetchrow(
        """
        SELECT
            uwa.id,
            uwa.account_name,
            uwa.account_number,
            uwa.is_default,
            wm.name AS method_name
        FROM user_withdraw_accounts uwa
        JOIN withdraw_methods wm
            ON wm.id = uwa.method_id
        WHERE
            uwa.id=$1
            AND uwa.user_id=$2
        """,
        account_id,
        call.from_user.id
    )

    if not account:
        return await call.answer(
            "Rekening tidak ditemukan.",
            show_alert=True
        )

    kb = InlineKeyboardBuilder()

    if not account["is_default"]:
        kb.button(
            text="⭐ Jadikan Utama",
            callback_data=f"withdraw_default:{account_id}"
        )

    kb.button(
        text="🗑 Hapus Rekening",
        callback_data=f"withdraw_delete:{account_id}"
    )

    kb.button(
        text="🔙 Kembali",
        callback_data="withdraw_accounts"
    )

    kb.adjust(1)

    status = "⭐ Rekening Utama" if account["is_default"] else "-"

    text = (
        "🏦 <b>DETAIL REKENING</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"Metode : <b>{account['method_name']}</b>\n"
        f"Nama : <b>{account['account_name']}</b>\n"
        f"Nomor : <code>{account['account_number']}</code>\n"
        f"Status : <b>{status}</b>"
    )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()

# =========================
# JADIKAN DEFAULT
# =========================

@router.callback_query(F.data.startswith("withdraw_default:"))
async def withdraw_default(call: CallbackQuery):

    account_id = int(call.data.split(":")[1])

    pool = await get_pool()

    account = await pool.fetchrow(
        """
        SELECT id
        FROM user_withdraw_accounts
        WHERE id=$1
          AND user_id=$2
        """,
        account_id,
        call.from_user.id
    )

    if not account:
        return await call.answer(
            "Rekening tidak ditemukan.",
            show_alert=True
        )

    # Hapus default lama
    await pool.execute(
        """
        UPDATE user_withdraw_accounts
        SET
            is_default=FALSE,
            updated_at=NOW()
        WHERE user_id=$1
        """,
        call.from_user.id
    )

    # Jadikan rekening ini default
    await pool.execute(
        """
        UPDATE user_withdraw_accounts
        SET
            is_default=TRUE,
            updated_at=NOW()
        WHERE id=$1
        """,
        account_id
    )

    await call.answer(
        "✅ Rekening utama berhasil diubah."
    )

    # Refresh halaman detail
    call.data = f"withdraw_account_detail:{account_id}"
    await withdraw_account_detail(call)

# =========================
# HAPUS REKENING
# =========================

@router.callback_query(F.data.startswith("withdraw_delete:"))
async def withdraw_delete(call: CallbackQuery):

    account_id = int(call.data.split(":")[1])

    pool = await get_pool()

    account = await pool.fetchrow(
        """
        SELECT
            id,
            is_default
        FROM user_withdraw_accounts
        WHERE
            id=$1
            AND user_id=$2
        """,
        account_id,
        call.from_user.id
    )

    if not account:
        return await call.answer(
            "Rekening tidak ditemukan.",
            show_alert=True
        )

    # Hapus rekening
    await pool.execute(
        """
        DELETE FROM user_withdraw_accounts
        WHERE id=$1
        """,
        account_id
    )

    # Jika yang dihapus rekening utama,
    # jadikan rekening pertama sebagai default
    if account["is_default"]:

        new_default = await pool.fetchval(
            """
            SELECT id
            FROM user_withdraw_accounts
            WHERE user_id=$1
            ORDER BY id
            LIMIT 1
            """,
            call.from_user.id
        )

        if new_default:

            await pool.execute(
                """
                UPDATE user_withdraw_accounts
                SET
                    is_default=TRUE,
                    updated_at=NOW()
                WHERE id=$1
                """,
                new_default
            )

    await call.answer(
        "✅ Rekening berhasil dihapus."
    )

    await withdraw_accounts(call)
    
