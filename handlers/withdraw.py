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
# DAFTAR REKENING
# =========================

@router.callback_query(F.data == "withdraw_accounts")
async def withdraw_accounts(call: CallbackQuery):

    pool = await get_pool()

    rows = await pool.fetch(
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

    kb = InlineKeyboardBuilder()

    if not rows:

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
                "🏦 <b>DAFTAR REKENING</b>\n"
                "━━━━━━━━━━━━━━\n\n"
                "Kamu belum memiliki rekening atau E-Wallet."
            ),
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

        return await call.answer()

    text = (
        "🏦 <b>DAFTAR REKENING</b>\n"
        "━━━━━━━━━━━━━━\n\n"
    )

    for i, row in enumerate(rows, start=1):

        status = " ⭐ Default" if row["is_default"] else ""

        text += (
            f"<b>{i}. {row['method_name']}</b>{status}\n"
            f"👤 {row['account_name']}\n"
            f"💳 <code>{row['account_number']}</code>\n\n"
        )

        if not row["is_default"]:
            kb.button(
                text=f"⭐ Default #{i}",
                callback_data=f"withdraw_default:{row['id']}"
            )

        kb.button(
            text=f"🗑 Hapus #{i}",
            callback_data=f"withdraw_delete:{row['id']}"
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
# SET DEFAULT REKENING
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

    # Nonaktifkan semua default
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
        "✅ Rekening default berhasil diubah."
    )

    # Refresh daftar rekening
    await withdraw_accounts(call)

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

    await pool.execute(
        """
        DELETE FROM user_withdraw_accounts
        WHERE id=$1
        """,
        account_id
    )

    # Jika yang dihapus adalah rekening default,
    # jadikan rekening pertama sebagai default.
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

    # Refresh daftar rekening
    await withdraw_accounts(call)

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
