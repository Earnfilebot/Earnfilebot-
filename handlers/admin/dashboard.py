from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
import pytz

from database import get_pool
from config import ADMIN_IDS


router = Router()


# =========================
# ADMIN CHECK
# =========================

def is_admin(user_id:int):
    return user_id in ADMIN_IDS


# =========================
# RUPIAH
# =========================

def rupiah(value):
    try:
        value = int(value or 0)
    except:
        value = 0

    return f"Rp {value:,}".replace(",", ".")



# =========================
# SAFE COUNT
# =========================

async def count_safe(pool, table):

    try:
        return await pool.fetchval(
            f"SELECT COUNT(*) FROM {table}"
        ) or 0

    except Exception:
        return 0



async def sum_safe(pool, column, table):

    try:
        return await pool.fetchval(
            f"""
            SELECT COALESCE(SUM({column}),0)
            FROM {table}
            """
        ) or 0

    except Exception:
        return 0



# =========================
# DASHBOARD TEXT
# =========================

async def dashboard_text():

    pool = await get_pool()


    users = await count_safe(
        pool,
        "users"
    )


    files = await count_safe(
        pool,
        "codes"
    )


    media = await count_safe(
        pool,
        "medias"
    )


    balance = await sum_safe(
        pool,
        "balance",
        "users"
    )


    revenue = await sum_safe(
        pool,
        "amount",
        "payments"
    )


    pending_payment = 0
    paid_payment = 0
    failed_payment = 0


    try:

        pending_payment = await pool.fetchval(
            """
            SELECT COUNT(*)
            FROM payments
            WHERE status='pending'
            """
        ) or 0


        paid_payment = await pool.fetchval(
            """
            SELECT COUNT(*)
            FROM payments
            WHERE status='paid'
            """
        ) or 0


        failed_payment = await pool.fetchval(
            """
            SELECT COUNT(*)
            FROM payments
            WHERE status='failed'
            """
        ) or 0


    except:
        pass



    now = datetime.now(
        pytz.timezone("Asia/Jakarta")
    ).strftime(
        "%d-%m-%Y %H:%M WIB"
    )


    return (
        "🛠 <b>ADMIN PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        "📊 <b>SYSTEM</b>\n\n"

        f"👤 User     : {users}\n"
        f"📂 Files    : {files}\n"
        f"🖼 Media    : {media}\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "💰 <b>FINANCE</b>\n\n"

        f"👛 Balance  : {rupiah(balance)}\n"
        f"💵 Revenue  : {rupiah(revenue)}\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "💳 <b>PAYMENT</b>\n"

        f"🟡 Pending : {pending_payment}\n"
        f"🟢 Paid    : {paid_payment}\n"
        f"🔴 Failed  : {failed_payment}\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        f"🕒 Update : {now}"
    )



# =========================
# BUTTON
# =========================

def dashboard_keyboard():

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
        callback_data="admin_payments"
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
        text="📢 Broadcast",
        callback_data="admin_broadcast"
    )


    kb.button(
        text="📜 Logs",
        callback_data="admin_logs"
    )


    kb.button(
        text="⚙️ Settings",
        callback_data="admin_settings"
    )


    kb.adjust(2)


    return kb.as_markup()



# =========================
# /admin COMMAND
# =========================

@router.message(Command("admin"))
async def admin_command(message:Message):

    if not is_admin(message.from_user.id):

        return await message.answer(
            "❌ Tidak punya akses"
        )


    text = await dashboard_text()


    await message.answer(
        text,
        reply_markup=dashboard_keyboard(),
        parse_mode="HTML"
    )



# =========================
# BUTTON HOME
# =========================

@router.callback_query(F.data=="admin_home")
async def admin_home(call:CallbackQuery):

    if not is_admin(call.from_user.id):
        return


    await call.message.edit_text(
        await dashboard_text(),
        reply_markup=dashboard_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()
