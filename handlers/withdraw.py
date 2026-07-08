from datetime import datetime
from zoneinfo import ZoneInfo
from config import ADMIN_IDS

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


# =========================
# MENU WITHDRAW
# =========================

@router.callback_query(F.data == "withdraw")
async def withdraw_menu(call: CallbackQuery):

    open_now = withdraw_is_open()

    kb = InlineKeyboardBuilder()

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
        WithdrawState.input_amount
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


@router.message(WithdrawState.input_amount)
async def input_withdraw_amount(
    message: Message,
    state: FSMContext
):

    if not message.text:

        return await message.answer(
            "❌ Kirim nominal withdraw."
        )


    amount_text = (
        message.text
        .replace(".", "")
        .replace(",", "")
        .replace("Rp", "")
        .replace("rp", "")
        .strip()
    )


    if not amount_text.isdigit():

        return await message.answer(
            "❌ Nominal tidak valid.\n\n"
            "Kirim angka saja.\n"
            "Contoh: 100000"
        )


    amount = int(amount_text)


    if amount < 100000:

        return await message.answer(
            "❌ Minimal withdraw adalah Rp 100.000."
        )


    pool = await get_pool()


    balance = await pool.fetchval(
        """
        SELECT balance
        FROM users
        WHERE telegram_id=$1
        """,
        message.from_user.id
    )


    if balance is None:
        balance = 0


    if balance < amount:

        return await message.answer(
            (
                "❌ Saldo tidak mencukupi.\n\n"
                f"Saldo kamu: Rp {balance:,}"
            ).replace(",", ".")
        )


    data = await state.get_data()


    fee = data.get(
        "withdraw_fee",
        2000
    )


    total_cut = amount + fee


    if balance < total_cut:

        return await message.answer(
            (
                "❌ Saldo tidak cukup untuk fee admin.\n\n"

                f"💰 Withdraw : Rp {amount:,}\n"
                f"💸 Fee : Rp {fee:,}\n"
                f"📉 Total potong : Rp {total_cut:,}"
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
    fee = data.get(
        "withdraw_fee",
        2000
    )


    balance = await pool.fetchval(
        """
        SELECT balance
        FROM users
        WHERE telegram_id=$1
        """,
        call.from_user.id
    )


    if balance is None or balance < amount + fee:

        await state.clear()

        return await call.answer(
            "Saldo tidak mencukupi.",
            show_alert=True
        )


    try:

        async with pool.acquire() as conn:

            async with conn.transaction():

                # POTONG SALDO

                await conn.execute(
                    """
                    UPDATE users
                    SET balance = balance - $1
                    WHERE telegram_id=$2
                    """,
                    amount + fee,
                    call.from_user.id
                )


                # SIMPAN WITHDRAW
                # SESUAI DATABASE KAMU

                await conn.execute(
                    """
                    INSERT INTO withdrawals
                    (
                        seller_id,
                        amount,
                        method,
                        account_name,
                        account_number,
                        status,
                        created_at
                    )
                    VALUES
                    ($1,$2,$3,$4,$5,'pending',NOW())
                    """,
                    call.from_user.id,
                    amount,
                    account["method_name"],
                    account["account_name"],
                    account["account_number"]
                )


    except Exception as e:

        print(
            "WITHDRAW CREATE ERROR:",
            e
        )

        return await call.answer(
            "Terjadi kesalahan saat membuat withdraw.",
            show_alert=True
        )


    # =========================
    # NOTIF ADMIN
    # =========================

    from main import bot
    from config import ADMIN_IDS


    for admin_id in ADMIN_IDS:

        try:

            kb_admin = InlineKeyboardBuilder()

            kb_admin.button(
                text="✅ Proses",
                callback_data=f"withdraw_process:{call.from_user.id}"
            )

            kb_admin.button(
                text="❌ Reject",
                callback_data=f"withdraw_reject:{call.from_user.id}"
            )

            kb_admin.adjust(2)


            await bot.send_message(
                admin_id,
                (
                    "🚨 <b>REQUEST WITHDRAW BARU</b>\n"
                    "━━━━━━━━━━━━━━\n\n"

                    f"👤 User ID : <code>{call.from_user.id}</code>\n"
                    f"📱 Username : @{call.from_user.username or '-'}\n\n"

                    f"🏦 Metode : <b>{account['method_name']}</b>\n"
                    f"👤 Nama : <b>{account['account_name']}</b>\n"
                    f"💳 Nomor : <code>{account['account_number']}</code>\n\n"

                    f"💰 Nominal : <b>Rp {amount:,}</b>\n"
                    f"💸 Fee : <b>Rp {fee:,}</b>\n\n"

                    "⏳ Status : <b>PENDING</b>"
                ).replace(",", "."),
                parse_mode="HTML",
                reply_markup=kb_admin.as_markup()
            )


        except Exception as e:

            print(
                "WITHDRAW ADMIN NOTIFY ERROR:",
                e
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

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🔙 Menu Withdraw",
        callback_data="withdraw"
    )

    kb.adjust(1)

    await call.message.edit_text(
        (
            "❌ <b>WITHDRAW DIBATALKAN</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            "Permintaan withdraw dibatalkan.\n"
            "Saldo kamu tidak berubah."
        ),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()
