from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_pool
from .dashboard import is_admin

router = Router()

@router.callback_query(F.data == "admin_users")
async def admin_users(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    kb = InlineKeyboardBuilder()

    kb.button(
        text="👤 Total User",
        callback_data="users_total"
    )

    kb.button(
        text="🆕 User Baru",
        callback_data="users_latest"
    )

    kb.button(
        text="🔍 Cari User",
        callback_data="users_search"
    )

    kb.button(
        text="💰 Balance",
        callback_data="users_balance"
    )

    kb.button(
        text="🚫 Ban User",
        callback_data="users_ban"
    )

    kb.button(
        text="✅ Unban",
        callback_data="users_unban"
    )

    kb.button(
        text="⬅ Back",
        callback_data="admin_home"
    )

    kb.adjust(2)

    await call.message.edit_text(
        "👤 <b>USER MANAGER</b>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()

@router.callback_query(F.data == "users_total")
async def users_total(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return

    pool = await get_pool()

    total = await pool.fetchval(
        "SELECT COUNT(*) FROM users"
    )

    await call.message.edit_text(
        f"👥 Total User : <b>{total}</b>",
        parse_mode="HTML"
    )
