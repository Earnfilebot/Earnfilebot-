import asyncio
import json

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_pool

router = Router()

# =========================
# ADMIN CONFIG
# =========================
ADMIN_IDS = [123456789]  # GANTI ID KAMU

def is_admin(user_id: int):
    return user_id in ADMIN_IDS


# =========================
# ADMIN MENU
# =========================
def admin_menu():
    kb = InlineKeyboardBuilder()

    kb.button(text="👤 Users", callback_data="adm_users")
    kb.button(text="💰 Payments", callback_data="adm_payments")
    kb.button(text="📦 Files", callback_data="adm_files")
    kb.button(text="📊 Stats", callback_data="adm_stats")
    kb.button(text="📢 Broadcast", callback_data="adm_broadcast")

    kb.adjust(2, 2, 1)
    return kb.as_markup()


# =========================
# /ADMIN
# =========================
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Akses ditolak")

    await message.answer("🛠 ADMIN PANEL", reply_markup=admin_menu())


# =========================
# USERS LIST
# =========================
@router.callback_query(F.data == "adm_users")
async def adm_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    pool = await get_pool()
    users = await pool.fetch("SELECT telegram_id, balance FROM users LIMIT 20")

    text = "👤 USERS (TOP 20)\n\n"
    for u in users:
        text += f"ID: {u['telegram_id']} | Balance: {u['balance']}\n"

    await call.message.edit_text(text, reply_markup=admin_menu())
    await call.answer()


# =========================
# PAYMENTS
# =========================
@router.callback_query(F.data == "adm_payments")
async def adm_payments(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    pool = await get_pool()
    data = await pool.fetch("""
        SELECT user_id, code, status, amount
        FROM payments
        ORDER BY id DESC
        LIMIT 10
    """)

    text = "💰 LAST PAYMENTS\n\n"
    for p in data:
        text += f"{p['user_id']} | {p['code']} | {p['status']} | {p['amount']}\n"

    await call.message.edit_text(text, reply_markup=admin_menu())
    await call.answer()


# =========================
# FILES
# =========================
@router.callback_query(F.data == "adm_files")
async def adm_files(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    pool = await get_pool()
    files = await pool.fetch("""
        SELECT code, price, seller_id
        FROM files
        ORDER BY id DESC
        LIMIT 10
    """)

    text = "📦 FILES\n\n"
    for f in files:
        text += f"{f['code']} | Rp{f['price']} | seller:{f['seller_id']}\n"

    await call.message.edit_text(text, reply_markup=admin_menu())
    await call.answer()


# =========================
# STATS
# =========================
@router.callback_query(F.data == "adm_stats")
async def adm_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    pool = await get_pool()

    users = await pool.fetchval("SELECT COUNT(*) FROM users")
    payments = await pool.fetchval("SELECT COUNT(*) FROM payments")
    paid = await pool.fetchval("SELECT COUNT(*) FROM payments WHERE status='paid'")

    text = (
        "📊 STATS\n\n"
        f"👤 Users: {users}\n"
        f"💰 Payments: {payments}\n"
        f"✅ Paid: {paid}\n"
    )

    await call.message.edit_text(text, reply_markup=admin_menu())
    await call.answer()


# =========================
# BROADCAST (simple version)
# =========================
@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    await call.message.answer("📢 Kirim pesan broadcast kamu sekarang")
    await call.answer()
