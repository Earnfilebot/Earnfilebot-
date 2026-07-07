from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_pool
from config import ADMIN_IDS


router = Router()


# =========================
# ADMIN CHECK
# =========================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS



# =========================
# FORMAT RUPIAH
# =========================

def rupiah(value):

    try:
        value = int(value or 0)
    except:
        value = 0

    return f"Rp {value:,}".replace(",", ".")



# =========================
# ADMIN DASHBOARD
# =========================

@router.callback_query(F.data == "admin_home")
async def admin_home(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return await call.answer(
            "❌ Tidak punya akses",
            show_alert=True
        )


    pool = await get_pool()


    # =====================
    # STAT USER
    # =====================

    total_user = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM users
        WHERE telegram_id IS NOT NULL
        """
    )


    total_vip = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM users
        WHERE vip = TRUE
        """
    )


    # =====================
    # BALANCE
    # =====================

    total_balance = await pool.fetchval(
        """
        SELECT COALESCE(SUM(balance),0)
        FROM users
        """
    )


    # =====================
    # PAYMENT
    # =====================

    try:
        pending_payment = await pool.fetchval(
            """
            SELECT COUNT(*)
            FROM payments
            WHERE status='pending'
            """
        )
    except:
        pending_payment = 0



    # =====================
    # WITHDRAW
    # =====================

    try:
        pending_withdraw = await pool.fetchval(
            """
            SELECT COUNT(*)
            FROM withdrawals
            WHERE status='pending'
            """
        )
    except:
        pending_withdraw = 0



    kb = InlineKeyboardBuilder()


    # USER

    kb.button(
        text="👤 Kelola User",
        callback_data="admin_users"
    )


    # PAYMENT

    kb.button(
        text=f"💳 Payment ({pending_payment})",
        callback_data="admin_payment"
    )


    # WITHDRAW

    kb.button(
        text=f"💸 Withdraw ({pending_withdraw})",
        callback_data="admin_withdraw"
    )


    # STAT

    kb.button(
        text="📊 Statistik Balance",
        callback_data="admin_balance_stats"
    )


    # LOG

    kb.button(
        text="📜 System Log",
        callback_data="admin_logs"
    )


    # BROADCAST

    kb.button(
        text="📢 Broadcast",
        callback_data="admin_broadcast"
    )


    # SETTINGS

    kb.button(
        text="⚙️ Settings",
        callback_data="admin_settings"
    )


    kb.adjust(2)



    text = (
        "👑 <b>ADMIN DASHBOARD</b>\n\n"

        f"👥 Total User : <b>{total_user}</b>\n"
        f"⭐ VVIP User : <b>{total_vip}</b>\n"
        f"💰 Total Balance : <b>{rupiah(total_balance)}</b>\n\n"

        f"💳 Pending Payment : <b>{pending_payment}</b>\n"
        f"💸 Pending Withdraw : <b>{pending_withdraw}</b>\n\n"

        "🟢 System Status : ONLINE"
    )


    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


    await call.answer()



# =========================
# BACK
# =========================

@router.callback_query(F.data == "back_admin")
async def back_admin(call: CallbackQuery):

    await admin_home(call)



# =========================
# BALANCE STAT PLACEHOLDER
# =========================

@router.callback_query(F.data == "admin_balance_stats")
async def balance_stats(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return


    pool = await get_pool()


    total = await pool.fetchval(
        """
        SELECT COALESCE(SUM(balance),0)
        FROM users
        """
    )


    await call.message.edit_text(
        f"📊 <b>STATISTIK BALANCE</b>\n\n"
        f"💰 Total Balance User:\n"
        f"<b>{rupiah(total)}</b>",
        parse_mode="HTML"
    )



# =========================
# LOG PLACEHOLDER
# =========================

@router.callback_query(F.data == "admin_logs")
async def admin_logs(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return


    await call.message.edit_text(
        "📜 <b>SYSTEM LOG</b>\n\n"
        "Belum ada log terbaru.",
        parse_mode="HTML"
    )
