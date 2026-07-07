from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
import asyncio

from database import get_pool

router = Router()

# =========================
# ADMIN CONFIG
# =========================
ADMIN_IDS = {6847035364}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# =========================
# FORMAT RUPIAH
# =========================
def rupiah(value: int) -> str:
    value = value or 0
    return f"Rp {value:,.0f}".replace(",", ".")


# =========================
# DASHBOARD MENU
# =========================
def dashboard_menu():
    kb = InlineKeyboardBuilder()

    buttons = [
        ("👤 Users", "admin_users"),
        ("📂 Files", "admin_files"),
        ("💳 Payment", "admin_payment"),
        ("🏧 Withdraw", "admin_withdraw"),
        ("💰 Balance", "admin_balance"),
        ("📊 Statistics", "admin_statistics"),
        ("📢 Broadcast", "admin_broadcast"),
        ("⚙ Settings", "admin_settings"),
        ("📝 Logs", "admin_logs"),
        ("🔐 Admin", "admin_admins"),
    ]

    for text, data in buttons:
        kb.button(text=text, callback_data=data)

    kb.adjust(2)
    return kb.as_markup()


# =========================
# DASHBOARD DATA
# =========================
async def get_dashboard_text() -> str:
    pool = await get_pool()

    (
        total_users,
        total_files,
        total_media,
        total_balance,
        revenue,
        payment_pending,
        payment_paid,
        payment_failed,
        withdraw_pending,
        withdraw_processing,
        withdraw_success,
        withdraw_reject
    ) = await asyncio.gather(

        pool.fetchval("SELECT COUNT(*) FROM users"),
        pool.fetchval("SELECT COUNT(*) FROM files"),

        # hitung total media dari JSON
        pool.fetchval("""
            SELECT COALESCE(SUM(jsonb_array_length(media::jsonb)), 0)
            FROM files
        """),

        pool.fetchval("SELECT COALESCE(SUM(balance), 0) FROM users"),
        pool.fetchval("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status='paid'"),

        pool.fetchval("SELECT COUNT(*) FROM payments WHERE status='pending'"),
        pool.fetchval("SELECT COUNT(*) FROM payments WHERE status='paid'"),
        pool.fetchval("SELECT COUNT(*) FROM payments WHERE status='failed'"),

        pool.fetchval("SELECT COUNT(*) FROM withdraws WHERE status='pending'"),
        pool.fetchval("SELECT COUNT(*) FROM withdraws WHERE status='processing'"),
        pool.fetchval("SELECT COUNT(*) FROM withdraws WHERE status='approved'"),
        pool.fetchval("SELECT COUNT(*) FROM withdraws WHERE status='rejected'"),
    )

    now = datetime.now().strftime("%d-%m-%Y %H:%M WIB")

    return (
        "🛠 <b>ADMIN PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        "📊 <b>SYSTEM</b>\n\n"
        f"👤 User     : <b>{total_users}</b>\n"
        f"📂 Files    : <b>{total_files}</b>\n"
        f"🖼 Media    : <b>{total_media}</b>\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "💰 <b>FINANCE</b>\n\n"
        f"👛 Balance  : <b>{rupiah(total_balance)}</b>\n"
        f"💵 Revenue  : <b>{rupiah(revenue)}</b>\n\n"

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


# =========================
# /ADMIN COMMAND
# =========================
@router.message(F.text == "/admin")
async def admin_dashboard(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Kamu bukan admin.")

    text = await get_dashboard_text()

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=dashboard_menu()
    )


# =========================
# ADMIN HOME (BUTTON)
# =========================
@router.callback_query(F.data == "admin_home")
async def admin_home(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("❌ No access", show_alert=True)

    text = await get_dashboard_text()

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=dashboard_menu()
    )

    await call.answer()
