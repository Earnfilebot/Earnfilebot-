from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from datetime import timedelta

from database import get_pool
from .dashboard import is_admin, rupiah

router = Router()


# =========================
# STATES
# =========================

class SearchUserState(StatesGroup):
    telegram_id = State()


class BalanceState(StatesGroup):
    waiting_user = State()


class BanUserState(StatesGroup):
    waiting_user = State()


class UnbanUserState(StatesGroup):
    waiting_user = State()


class VvipState(StatesGroup):
    waiting_user = State()
    waiting_days = State()


# =========================
# MENU USER
# =========================

@router.callback_query(F.data == "admin_users")
async def admin_users(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    kb = InlineKeyboardBuilder()

    kb.button(text="👤 Total User", callback_data="users_total")
    kb.button(text="🆕 User Baru", callback_data="users_latest")
    kb.button(text="🔍 Cari User", callback_data="users_search")
    kb.button(text="💰 Balance User", callback_data="users_balance")
    kb.button(text="🚫 Ban User", callback_data="users_ban")
    kb.button(text="✅ Unban User", callback_data="users_unban")
    kb.button(text="👑 Set VVIP", callback_data="users_vvip")
    kb.button(text="⬅ Back", callback_data="admin_home")

    kb.adjust(2)

    await call.message.edit_text(
        "👤 <b>USER MANAGER</b>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()


# =========================
# BACK BUTTON GLOBAL
# =========================

@router.callback_query(F.data == "back_users")
async def back_users(call: CallbackQuery):
    await admin_users(call)


# =========================
# TOTAL USERS
# =========================

@router.callback_query(F.data == "users_total")
async def users_total(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    pool = await get_pool()
    total = await pool.fetchval("SELECT COUNT(*) FROM users")

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ Kembali", callback_data="admin_users")

    await call.message.edit_text(
        f"👥 <b>TOTAL USER</b>\n\nTotal: <b>{total}</b>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()


# =========================
# LATEST USERS
# =========================

@router.callback_query(F.data == "users_latest")
async def users_latest(call: CallbackQuery):

    pool = await get_pool()

    users = await pool.fetch("""
        SELECT telegram_id, balance, created_at
        FROM users
        ORDER BY created_at DESC
        LIMIT 10
    """)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ Kembali", callback_data="admin_users")

    if not users:
        return await call.message.edit_text("❌ Tidak ada user", reply_markup=kb.as_markup())

    text = "🆕 <b>10 USER TERBARU</b>\n\n"

    for i, u in enumerate(users, 1):
        tgl = u["created_at"].strftime("%d-%m-%Y %H:%M")

        text += (
            f"{i}. <code>{u['telegram_id']}</code>\n"
            f"💰 {rupiah(u['balance'])}\n"
            f"📅 {tgl}\n\n"
        )

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())


# =========================
# SEARCH USER
# =========================

@router.callback_query(F.data == "users_search")
async def users_search(call: CallbackQuery, state: FSMContext):

    await state.set_state(SearchUserState.telegram_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ Kembali", callback_data="admin_users")

    await call.message.edit_text(
        "🔍 Kirim Telegram ID user:",
        reply_markup=kb.as_markup()
    )

    await call.answer()


@router.message(SearchUserState.telegram_id)
async def process_search(message: Message, state: FSMContext):

    pool = await get_pool()

    if not message.text.isdigit():
        return await message.answer("❌ Harus angka")

    user = await pool.fetchrow(
        "SELECT * FROM users WHERE telegram_id=$1",
        int(message.text)
    )

    if not user:
        await state.clear()
        return await message.answer("❌ User tidak ditemukan")

    text = (
        "👤 <b>USER DETAIL</b>\n\n"
        f"ID: <code>{user['telegram_id']}</code>\n"
        f"Balance: {rupiah(user['balance'])}\n"
    )

    await message.answer(text, parse_mode="HTML")
    await state.clear()


# =========================
# BALANCE USER
# =========================

@router.callback_query(F.data == "users_balance")
async def users_balance(call: CallbackQuery, state: FSMContext):

    await state.set_state(BalanceState.waiting_user)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ Kembali", callback_data="admin_users")

    await call.message.edit_text(
        "💰 Kirim Telegram ID user:",
        reply_markup=kb.as_markup()
    )

    await call.answer()


@router.message(BalanceState.waiting_user)
async def balance_user(message: Message, state: FSMContext):

    pool = await get_pool()

    if not message.text.isdigit():
        return await message.answer("❌ Harus angka")

    user = await pool.fetchrow(
        "SELECT * FROM users WHERE telegram_id=$1",
        int(message.text)
    )

    if not user:
        await state.clear()
        return await message.answer("❌ User tidak ditemukan")

    await message.answer(
        f"💰 Balance: {rupiah(user['balance'])}"
    )

    await state.clear()


# =========================
# BAN
# =========================

@router.callback_query(F.data == "users_ban")
async def users_ban(call: CallbackQuery, state: FSMContext):

    await state.set_state(BanUserState.waiting_user)

    await call.message.edit_text(
        "🚫 Kirim Telegram ID / username"
    )

    await call.answer()


@router.message(BanUserState.waiting_user)
async def ban_user(message: Message, state: FSMContext):

    pool = await get_pool()

    key = message.text.strip()

    if key.isdigit():
        user = await pool.fetchrow("SELECT * FROM users WHERE telegram_id=$1", int(key))
    else:
        user = await pool.fetchrow("SELECT * FROM users WHERE LOWER(username)=LOWER($1)", key.replace("@", ""))

    if not user:
        await state.clear()
        return await message.answer("❌ Tidak ditemukan")

    await pool.execute(
        "UPDATE users SET is_banned=TRUE WHERE telegram_id=$1",
        user["telegram_id"]
    )

    await message.answer("🚫 User diban")
    await state.clear()


# =========================
# UNBAN
# =========================

@router.callback_query(F.data == "users_unban")
async def users_unban(call: CallbackQuery, state: FSMContext):

    await state.set_state(UnbanUserState.waiting_user)

    await call.message.edit_text("✅ Kirim ID / username")

    await call.answer()


@router.message(UnbanUserState.waiting_user)
async def unban_user(message: Message, state: FSMContext):

    pool = await get_pool()

    key = message.text.strip()

    if key.isdigit():
        user = await pool.fetchrow("SELECT * FROM users WHERE telegram_id=$1", int(key))
    else:
        user = await pool.fetchrow("SELECT * FROM users WHERE LOWER(username)=LOWER($1)", key.replace("@", ""))

    if not user:
        await state.clear()
        return await message.answer("❌ Tidak ditemukan")

    await pool.execute(
        "UPDATE users SET is_banned=FALSE WHERE telegram_id=$1",
        user["telegram_id"]
    )

    await message.answer("✅ User unban")
    await state.clear()


# =========================
# VVIP SYSTEM (FULL FIX)
# =========================

@router.callback_query(F.data == "users_vvip")
async def vvip_start(call: CallbackQuery, state: FSMContext):

    await state.clear()
    await state.set_state(VvipState.waiting_user)

    await call.message.edit_text("👑 Kirim user ID / username")
    await call.answer()


# =========================
# GET USER
# =========================
@router.message(VvipState.waiting_user)
async def vvip_user(message: Message, state: FSMContext):

    pool = await get_pool()
    key = message.text.strip()

    user = None

    if key.isdigit():
        user = await pool.fetchrow(
            "SELECT telegram_id FROM users WHERE telegram_id=$1",
            int(key)
        )
    else:
        user = await pool.fetchrow(
            "SELECT telegram_id FROM users WHERE LOWER(username)=LOWER($1)",
            key.replace("@", "")
        )

    if not user:
        await state.clear()
        return await message.answer("❌ User tidak ditemukan")

    await state.update_data(user_id=user["telegram_id"])
    await state.set_state(VvipState.waiting_days)

    await message.answer("📅 Masukkan durasi VVIP (hari)")


# =========================
# SET VVIP DAYS (FIXED)
# =========================

@router.message(VvipState.waiting_days)
async def vvip_set_days(message: Message, state: FSMContext):

    if not message.text or not message.text.isdigit():
        return await message.answer("❌ Harus angka (hari)")

    days = int(message.text)
    data = await state.get_data()
    user_id = data.get("user_id")

    if not user_id:
        await state.clear()
        return await message.answer("❌ Session error, ulangi lagi")

    pool = await get_pool()

    await pool.execute(
        """
        UPDATE users
        SET vip = TRUE,
            vip_until = NOW() + $2
        WHERE telegram_id = $1
        """,
        user_id,
        timedelta(days=days)
    )

    await message.answer(f"👑 VVIP aktif selama {days} hari")
    await state.clear()
