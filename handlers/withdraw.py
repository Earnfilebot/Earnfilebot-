from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from datetime import datetime, time
import pytz

from database import fetchrow, fetch
from aiogram.fsm.context import FSMContext
from states import WithdrawState

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
        InlineKeyboardButton(text="📜 History", callback_data="wd_history")
    )

    kb.row(
        InlineKeyboardButton(text="🔙 Kembali", callback_data="back_menu")
    )

    return kb.as_markup()


# =========================
# DASHBOARD
# =========================
@router.callback_query(F.data == "withdraw")
async def withdraw_dashboard(call: CallbackQuery):
    user_id = call.from_user.id

    # saldo user
    user = await fetchrow(
        "SELECT balance FROM users WHERE telegram_id=$1",
        user_id
    )
    balance = user["balance"] if user else 0

    # data withdraw
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
        f"⏳ Pending: Rp {pending:,}\n"
        f"⚙️ Process: Rp {process:,}\n"
        f"❌ Failed: Rp {failed:,}\n"
        f"✅ Success: Rp {success:,}\n\n"
        "🕒 Jam Operasional: 09:00 - 19:00 WIB\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔒 <b>Keamanan & Transparansi</b>\n"
        "• Sistem otomatis & real-time\n"
        "• Semua transaksi tercatat\n"
        "• Data rekening aman\n\n"
        "⚡ <b>Proses Cepat</b>\n"
        "• Maksimal 1x24 jam\n"
        "• Biasanya hanya beberapa jam\n\n"
        "💸 <b>Sistem Saldo</b>\n"
        "• Saldo langsung terpotong\n"
        "• Reject = saldo kembali 100%\n\n"
        "📌 <b>Tips</b>\n"
        "• Gunakan rekening valid\n"
        "• Nama harus sesuai rekening\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    await call.message.edit_text(
        text,
        reply_markup=withdraw_menu_kb(),
        parse_mode="HTML"
    )


# =========================
# WITHDRAW CLOSED
# =========================
@router.callback_query(F.data == "wd_closed")
async def wd_closed(call: CallbackQuery):
    await call.answer("Withdraw hanya buka jam 09:00 - 19:00 WIB", show_alert=True)


# =========================
# HISTORY (simple)
# =========================
@router.callback_query(F.data == "wd_history")
async def wd_history(call: CallbackQuery):
    user_id = call.from_user.id

    rows = await fetch(
        """
        SELECT amount, status, created_at
        FROM withdraw_requests
        WHERE user_id=$1
        ORDER BY created_at DESC
        LIMIT 10
        """,
        user_id
    )

    if not rows:
        text = "📜 Belum ada history withdraw"
    else:
        text = "📜 <b>History Withdraw</b>\n\n"
        for r in rows:
            text += f"Rp{r['amount']:,} | {r['status']} | {r['created_at']}\n"

    await call.message.edit_text(
        text,
        reply_markup=withdraw_menu_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "wd_setting")
async def withdraw_setting(call: CallbackQuery):
    user_id = call.from_user.id

    data = await fetchrow(
        "SELECT bank_name, account_number, account_name FROM withdraw_accounts WHERE user_id=$1",
        user_id
    )

    if data:
        text = (
            "⚙️ <b>SETTING PENARIKAN</b>\n\n"
            f"🏦 Bank/E-Wallet: {data['bank_name']}\n"
            f"💳 Nomor: {data['account_number']}\n"
            f"👤 Nama: {data['account_name']}\n\n"
            "Silakan update jika ada perubahan"
        )
    else:
        text = (
            "⚙️ <b>SETTING PENARIKAN</b>\n\n"
            "❌ Kamu belum menambahkan rekening\n\n"
            "Tambahkan dulu sebelum withdraw"
        )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✏️ Edit / Tambah", callback_data="wd_set_input")
    )
    kb.row(
        InlineKeyboardButton(text="🔙 Kembali", callback_data="withdraw")
    )

    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "wd_set_input")
async def set_account_start(call: CallbackQuery, state: FSMContext):
    await state.set_state("WAIT_ACCOUNT")

    await call.message.edit_text(
        "Masukkan data rekening:\n\nFormat:\nBank - Nomor - Nama\n\nContoh:\nBCA - 123456789 - Andi"
    )
    await call.answer()

@router.message()
async def save_account(message: Message, state: FSMContext):
    current = await state.get_state()

    if current != "WAIT_ACCOUNT":
        return

    try:
        bank, number, name = message.text.split(" - ")
    except:
        await message.answer("❌ Format salah!\nGunakan:\nBank - Nomor - Nama")
        return

    await execute(
        """
        INSERT INTO withdraw_accounts (user_id, bank_name, account_number, account_name)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id)
        DO UPDATE SET
            bank_name=$2,
            account_number=$3,
            account_name=$4
        """,
        message.from_user.id, bank, number, name
    )

    await state.clear()

    await message.answer("✅ Rekening berhasil disimpan")
