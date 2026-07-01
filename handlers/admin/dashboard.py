from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from database import get_pool

router = Router()

# =========================
# ADMIN CONFIG
# =========================

ADMIN_IDS = [
    6847035364,
]

def is_admin(user_id: int):
    return user_id in ADMIN_IDS


# =========================
# FORMAT RUPIAH
# =========================

def rupiah(value):
    if value is None:
        value = 0
    return f"Rp{value:,}".replace(",", ".")


# =========================
# DASHBOARD MENU
# =========================

def dashboard_menu():

    kb = InlineKeyboardBuilder()

    ...

# =========================
# DASHBOARD MENU
# =========================

def dashboard_menu():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="👤 Users",
        callback_data="admin_users"
    )

    kb.button(
        text="📂 Files",
        callback_data="admin_files"
    )

    kb.button(
        text="💳 Payment",
        callback_data="admin_payment"
    )

    kb.button(
        text="🏧 Withdraw",
        callback_data="admin_withdraw"
    )

    kb.button(
        text="💰 Balance",
        callback_data="admin_balance"
    )

    kb.button(
        text="📊 Statistics",
        callback_data="admin_statistics"
    )

    kb.button(
        text="📢 Broadcast",
        callback_data="admin_broadcast"
    )

    kb.button(
        text="⚙ Settings",
        callback_data="admin_settings"
    )

    kb.button(
        text="📝 Logs",
        callback_data="admin_logs"
    )

    kb.button(
        text="🔐 Admin",
        callback_data="admin_admins"
    )

    kb.adjust(2)

    return kb.as_markup()

# =========================
# ADMIN DASHBOARD
# =========================

@router.message(F.text == "/admin")
async def admin_dashboard(message: Message):

    if not is_admin(message.from_user.id):
        return await message.answer("❌ Kamu bukan admin.")

    pool = await get_pool()

    # USER
    total_users = await pool.fetchval(
        "SELECT COUNT(*) FROM users"
    )

    # FILE
    total_files = await pool.fetchval(
        "SELECT COUNT(*) FROM files"
    )

    # MEDIA
    total_media = await pool.fetchval(
        """
        SELECT COALESCE(SUM(media_count),0)
        FROM files
        """
    )

    # TOTAL BALANCE
    total_balance = await pool.fetchval(
        """
        SELECT COALESCE(SUM(balance),0)
        FROM users
        """
    )

    # PAYMENT
    payment_pending = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM payments
        WHERE status='pending'
        """
    )

    payment_paid = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM payments
        WHERE status='paid'
        """
    )

    payment_failed = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM payments
        WHERE status='failed'
        """
    )

    # WITHDRAW
    withdraw_pending = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM withdraws
        WHERE status='pending'
        """
    )

    withdraw_processing = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM withdraws
        WHERE status='processing'
        """
    )

    withdraw_success = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM withdraws
        WHERE status='approved'
        """
    )

    withdraw_reject = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM withdraws
        WHERE status='rejected'
        """
    )

    # REVENUE
    revenue = await pool.fetchval(
        """
        SELECT COALESCE(SUM(amount),0)
        FROM payments
        WHERE status='paid'
        """
    )

    now = datetime.now().strftime("%d-%m-%Y %H:%M WIB")

    text = (
        "🛠 <b>ADMIN PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        "📊 <b>SYSTEM</b>\n\n"

        f"👤 User        : <b>{total_users}</b>\n"
        f"📂 Folder      : <b>{total_files}</b>\n"
        f"🖼 Media       : <b>{total_media}</b>\n"
        f"🔑 Code        : <b>{total_files}</b>\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "💰 <b>FINANCE</b>\n\n"

        f"👛 Balance     : <b>{rupiah(total_balance)}</b>\n"
        f"💵 Revenue     : <b>{rupiah(revenue)}</b>\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "💳 <b>PAYMENT</b>\n"

        f"🟡 Pending : {payment_pending}\n"
        f"🟢 Paid    : {payment_paid}\n"
        f"🔴 Failed  : {payment_failed}\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "🏧 <b>WITHDRAW</b>\n"

        f"🟡 Pending : {withdraw_pending}\n"
        f"🔵 Process : {withdraw_processing}\n"
        f"🟢 Success : {withdraw_success}\n"
        f"🔴 Reject  : {withdraw_reject}\n\n"

        f"🕒 Update : {now}"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=dashboard_menu()
    )

