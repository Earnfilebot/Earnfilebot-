from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from datetime import datetime, time
import pytz

from states import WithdrawState
from database import fetchrow, fetch, execute, transaction
from config import GROUP_ID

router = Router()

# =========================
# TIMEZONE (WIB)
# =========================
tz = pytz.timezone("Asia/Jakarta")


def is_withdraw_open():
    now = datetime.now(tz).time()
    return time(9, 0) <= now <= time(19, 0)


# =========================
# KEYBOARD
# =========================
def withdraw_menu_kb():
    kb = InlineKeyboardBuilder()

    if is_withdraw_open():
        kb.row(
            InlineKeyboardButton(text="💸 Withdraw", callback_data="wd_start")
        )
    else:
        kb.row(
            InlineKeyboardButton(text="🔒 Withdraw (Tutup)", callback_data="wd_closed")
        )

    kb.row(
        InlineKeyboardButton(text="⚙️ Setting", callback_data="wd_setting")
    )

    kb.row(
        InlineKeyboardButton(text="🔙 Kembali", callback_data="back_menu")
    )

    return kb.as_markup()


# =========================
# DASHBOARD WITHDRAW
# =========================
@router.callback_query(F.data == "withdraw")
async def withdraw_dashboard(call: CallbackQuery):
    user_id = call.from_user.id

    # Ambil saldo utama
    user = await fetchrow(
        "SELECT balance FROM users WHERE telegram_id=$1",
        user_id
    )

    balance = user["balance"] if user else 0

    # Ambil data withdraw
    data = await fetch(
        """
        SELECT status, SUM(amount) as total
        FROM withdraw_requests
        WHERE user_id=$1
        GROUP BY status
        """,
        user_id
    )

    pending = 0
    process = 0
    failed = 0
    success = 0

    for row in data:
        if row["status"] == "pending":
            pending = row["total"] or 0
        elif row["status"] == "process":
            process = row["total"] or 0
        elif row["status"] == "failed":
            failed = row["total"] or 0
        elif row["status"] == "success":
            success = row["total"] or 0

    text = (
        "💰 <b>WITHDRAW DASHBOARD</b>\n\n"
        f"💳 Saldo Saat Ini: Rp {balance:,}\n"
        f"⏳ Saldo Pending: Rp {pending:,}\n"
        f"⚙️ Saldo Process: Rp {process:,}\n"
        f"❌ Saldo Failed: Rp {failed:,}\n"
        f"✅ Total Success: Rp {success:,}\n\n"
        "🕒 Jam Withdraw: 09:00 - 19:00 WIB"
    )

    await call.message.edit_text(
        text,
        reply_markup=withdraw_menu_kb()
    )

    await call.answer()


# =========================
# WD CLOSED ALERT
# =========================
@router.callback_query(F.data == "wd_closed")
async def wd_closed(call: CallbackQuery):
    await call.answer(
        "⏰ Withdraw buka jam 09:00 - 19:00 WIB",
        show_alert=True
    )


# =========================
# START WITHDRAW
# =========================
@router.callback_query(F.data == "wd_start")
async def withdraw_start(call: CallbackQuery, state: FSMContext):

    if not is_withdraw_open():
        return await call.answer(
            "⏰ Withdraw hanya buka jam 09:00 - 19:00 WIB",
            show_alert=True
        )

    await state.set_state(WithdrawState.amount)

    await call.message.edit_text(
        "💸 <b>WITHDRAW</b>\n\n"
        "Masukkan jumlah withdraw\n"
        "Contoh: 50000"
    )

    await call.answer()


# =========================
# INPUT NOMINAL
# =========================
@router.message(WithdrawState.amount)
async def process_withdraw(message: Message, state: FSMContext):

    # Proteksi jam
    if not is_withdraw_open():
        await state.clear()
        return await message.reply(
            "⏰ Withdraw sudah tutup\nBuka jam 09:00 - 19:00 WIB"
        )

    # Validasi angka
    try:
        amount = int(message.text)
    except:
        return await message.reply("❌ Masukkan angka yang valid")

    if amount < 10000:
        return await message.reply("❌ Minimal withdraw Rp 10.000")

    user_id = message.from_user.id

    # Ambil saldo
    user = await fetchrow(
        "SELECT balance FROM users WHERE telegram_id=$1",
        user_id
    )

    if not user:
        return await message.reply("❌ User tidak ditemukan")

    if user["balance"] < amount:
        return await message.reply("❌ Saldo tidak cukup")

    # Cek pending
    pending = await fetchrow(
        "SELECT id FROM withdraw_requests WHERE user_id=$1 AND status='pending'",
        user_id
    )

    if pending:
        return await message.reply("❌ Masih ada withdraw pending")

    # TRANSACTION
    try:
        await transaction([
            (
                "UPDATE users SET balance = balance - $1 WHERE telegram_id=$2",
                amount, user_id
            ),
            (
                "INSERT INTO withdraw_requests(user_id, amount, status) VALUES($1,$2,'pending')",
                user_id, amount
            )
        ])
    except Exception as e:
        return await message.reply("❌ Terjadi kesalahan")

    await state.clear()

    # RESPON USER
    await message.answer(
        "✅ <b>Withdraw berhasil diajukan</b>\n\n"
        f"💸 Jumlah: Rp {amount:,}\n"
        "⏳ Status: Pending"
    )

    # NOTIF ADMIN
    try:
        await message.bot.send_message(
            GROUP_ID,
            "💸 <b>REQUEST WITHDRAW</b>\n\n"
            f"👤 User: <code>{user_id}</code>\n"
            f"💰 Jumlah: Rp {amount:,}\n"
            "📌 Status: Pending"
        )
    except:
        pass


# =========================
# SETTING (SIMPLE PLACEHOLDER)
# =========================
@router.callback_query(F.data == "wd_setting")
async def wd_setting(call: CallbackQuery):
    await call.answer("⚙️ Fitur setting belum dibuat", show_alert=True)
