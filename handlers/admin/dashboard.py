from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

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

    text = (
        "🛠 <b>ADMIN PANEL</b>\n\n"
        "📊 <b>DASHBOARD</b>\n\n"
        f"👤 Total User : <b>{total_users}</b>\n"
        f"📂 Total File : <b>{total_files}</b>\n"
        f"🖼 Total Media : <b>{total_media}</b>\n\n"
        f"💰 Total Balance : <b>Rp{total_balance:,}</b>\n\n"
        "💳 <b>Payment</b>\n"
        f"• Pending : {payment_pending}\n"
        f"• Paid : {payment_paid}\n"
        f"• Failed : {payment_failed}\n\n"
        "🏧 <b>Withdraw</b>\n"
        f"• Pending : {withdraw_pending}\n"
        f"• Processing : {withdraw_processing}\n"
        f"• Success : {withdraw_success}\n"
        f"• Reject : {withdraw_reject}\n\n"
        f"💵 Revenue : <b>Rp{revenue:,}</b>"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=dashboard_menu()
    )
