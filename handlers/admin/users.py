from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_pool
from .dashboard import is_admin
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

router = Router()

class SearchUserState(StatesGroup):
    telegram_id = State()

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

    kb = InlineKeyboardBuilder()

    kb.button(
        text="⬅ Kembali",
        callback_data="admin_users"
    )

    await call.message.edit_text(
        f"👥 <b>TOTAL USER</b>\n\n"
        f"Total User : <b>{total}</b>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()

@router.callback_query(F.data == "users_latest")
async def users_latest(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    pool = await get_pool()

    users = await pool.fetch("""
        SELECT telegram_id, balance, created_at
        FROM users
        ORDER BY created_at DESC
        LIMIT 10
    """)

    kb = InlineKeyboardBuilder()

    kb.button(
        text="⬅ Kembali",
        callback_data="admin_users"
    )

    if not users:
        return await call.message.edit_text(
            "❌ Belum ada user.",
            reply_markup=kb.as_markup()
        )

    text = "🆕 <b>10 USER TERBARU</b>\n\n"

    for i, user in enumerate(users, start=1):
        waktu = user["created_at"].strftime("%d-%m-%Y %H:%M")

        text += (
            f"{i}. <code>{user['telegram_id']}</code>\n"
            f"💰 Balance : Rp{user['balance']:,}\n"
            f"📅 {waktu}\n\n"
        )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()

@router.callback_query(F.data == "users_search")
async def users_search(call: CallbackQuery, state: FSMContext):

    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    await state.set_state(SearchUserState.telegram_id)

    await call.message.answer(
        "🔍 Kirim Telegram ID user yang ingin dicari."
    )

    await call.answer()

@router.message(SearchUserState.telegram_id)
async def process_search(message: Message, state: FSMContext):

    if not is_admin(message.from_user.id):
        return

    if not message.text.isdigit():
        return await message.answer(
            "❌ Telegram ID harus berupa angka."
        )

    telegram_id = int(message.text)

    pool = await get_pool()

    user = await pool.fetchrow("""
        SELECT *
        FROM users
        WHERE telegram_id=$1
    """, telegram_id)

    if not user:
        await state.clear()
        return await message.answer(
            "❌ User tidak ditemukan."
        )

    text = (
        "👤 <b>USER DETAIL</b>\n\n"

        f"🆔 ID : <code>{user['telegram_id']}</code>\n"
        f"💰 Balance : Rp{user['balance']:,}\n"
    )

    if "username" in user:
        text += f"👤 Username : @{user['username']}\n"

    if "created_at" in user and user["created_at"]:
        text += (
            f"📅 Daftar : "
            f"{user['created_at'].strftime('%d-%m-%Y %H:%M')}\n"
        )

    await message.answer(
        text,
        parse_mode="HTML"
    )

    await state.clear()


