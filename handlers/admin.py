import asyncio

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_pool

router = Router()

# =========================
# ADMIN CONFIG
# =========================
ADMIN_IDS = [6847035364]  # GANTI ID KAMU

def is_admin(user_id: int):
    return user_id in ADMIN_IDS


# =========================
# FSM BROADCAST
# =========================
class BroadcastState(StatesGroup):
    message = State()


# =========================
# ADMIN MENU
# =========================
def admin_menu():
    kb = InlineKeyboardBuilder()

    kb.button(text="👤 Users", callback_data="adm_users")
    kb.button(text="💰 Payments", callback_data="adm_payments")
    kb.button(text="📦 Files", callback_data="adm_files")
    kb.button(text="📊 Stats", callback_data="adm_stats")
    kb.button(text="💸 Refund", callback_data="adm_refund")
    kb.button(text="🏧 Withdraw", callback_data="adm_withdraw")
    kb.button(text="📢 Broadcast", callback_data="adm_broadcast")

    kb.adjust(2, 2, 2, 1)
    return kb.as_markup()


# =========================
# /ADMIN
# =========================
@router.message(Command("admin"))
async def admin_panel(message: Message):
    print("ADMIN HIT", message.from_user.id)

    if not is_admin(message.from_user.id):
        print("NOT ADMIN")
        return await message.answer("❌ Akses ditolak")

    print("ADMIN OK")

    await message.answer(
        "🛠 ADMIN PANEL MARKETPLACE",
        reply_markup=admin_menu()
    )


# =========================
# USERS
# =========================
@router.callback_query(F.data == "adm_users")
async def adm_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    pool = await get_pool()
    users = await pool.fetch("""
        SELECT telegram_id, balance
        FROM users
        ORDER BY balance DESC
        LIMIT 20
    """)

    text = "👤 USERS TOP BALANCE\n\n"
    for u in users:
        text += f"{u['telegram_id']} | Rp{u['balance']}\n"

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
        SELECT user_id, code, amount, status, created_at
        FROM payments
        ORDER BY id DESC
        LIMIT 15
    """)

    text = "💰 TRANSACTIONS\n\n"
    for p in data:
        text += f"{p['user_id']} | {p['code']} | {p['status']} | Rp{p['amount']}\n"

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

    try:
        files = await pool.fetch("""
            SELECT code, price, seller_id
            FROM files
            ORDER BY code DESC
            LIMIT 15
        """)
    except Exception as e:
        return await call.message.edit_text(f"❌ ERROR:\n{e}")

    if not files:
        return await call.message.edit_text(
            "❌ Belum ada file",
            reply_markup=admin_menu()
        )

    text = "📦 FILES\n\n"

    for f in files:
        line = f"{f['code']} | Rp{f['price']} | seller:{f['seller_id']}\n"

        if len(text) + len(line) > 4000:
            break

        text += line

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
    revenue = await pool.fetchval("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid'")

    text = (
        "📊 SALES STATISTICS\n\n"
        f"👤 Users: {users}\n"
        f"💰 Total Payments: {payments}\n"
        f"✅ Paid: {paid}\n"
        f"💸 Revenue: Rp{revenue}\n"
    )

    await call.message.edit_text(text, reply_markup=admin_menu())
    await call.answer()


# =========================
# REFUND
# =========================
@router.callback_query(F.data == "adm_refund")
async def adm_refund(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    pool = await get_pool()

    data = await pool.fetch("""
        SELECT user_id, code, amount
        FROM payments
        WHERE status='paid'
        ORDER BY id DESC
        LIMIT 10
    """)

    text = "💸 REFUND LIST\n\n"
    for p in data:
        text += f"- {p['user_id']} | {p['code']} | Rp{p['amount']}\n"

    text += "\nSQL:\nUPDATE payments SET status='refunded' WHERE code='XXX';"

    await call.message.edit_text(text, reply_markup=admin_menu())
    await call.answer()


# =========================
# BROADCAST STEP 1
# =========================
@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    await state.set_state(BroadcastState.message)
    await call.message.answer("📢 Kirim pesan broadcast sekarang:")
    await call.answer()


# =========================
# BROADCAST STEP 2
# =========================
@router.message(BroadcastState.message)
async def send_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    pool = await get_pool()
    users = await pool.fetch("SELECT telegram_id FROM users")

    count = 0
    for u in users:
        try:
            await message.bot.send_message(u["telegram_id"], message.text)
            count += 1
            await asyncio.sleep(0.05)
        except:
            pass

    await message.answer(f"✅ Broadcast terkirim ke {count} user")
    await state.clear()


# =========================
# WITHDRAW LIST
# =========================
@router.callback_query(F.data == "adm_withdraw")
async def adm_withdraw(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    pool = await get_pool()

    data = await pool.fetch("""
        SELECT id, user_id, amount, method, account, status
        FROM withdraws
        WHERE status='pending'
        ORDER BY created_at DESC
        LIMIT 10
    """)

    if not data:
        return await call.message.edit_text(
            "❌ Tidak ada request withdraw",
            reply_markup=admin_menu()
        )

    text = "🏧 WITHDRAW REQUEST\n\n"
    kb = InlineKeyboardBuilder()

    for w in data:
        text += (
            f"ID: {w['id']}\n"
            f"User: {w['user_id']}\n"
            f"Amount: Rp{w['amount']}\n"
            f"Method: {w['method']}\n"
            f"Account: {w['account']}\n"
            f"Status: {w['status']}\n"
            "────────────\n"
        )

        kb.button(text=f"✅ {w['id']}", callback_data=f"wd_ok_{w['id']}")
        kb.button(text=f"❌ {w['id']}", callback_data=f"wd_no_{w['id']}")

    kb.adjust(2)

    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


# =========================
# APPROVE WITHDRAW (FIXED)
# =========================
@router.callback_query(F.data.startswith("wd_ok_"))
async def wd_ok(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    wid = int(call.data.split("_")[2])
    pool = await get_pool()

    data = await pool.fetchrow("""
        SELECT user_id, amount, status
        FROM withdraws
        WHERE id=$1
    """, wid)

    if not data:
        return await call.answer("Withdraw tidak ditemukan")

    if data["status"] != "pending":
        return await call.answer("Sudah diproses")

    await pool.execute("""
        UPDATE withdraws
        SET status='approved'
        WHERE id=$1
    """, wid)

    try:
        await call.bot.send_message(
            data["user_id"],
            f"✅ Withdraw Rp{data['amount']:,} telah disetujui"
        )
    except:
        pass

    await call.answer("✅ Approved")
    await call.message.delete()


# =========================
# REJECT WITHDRAW + REFUND (FIXED)
# =========================
@router.callback_query(F.data.startswith("wd_no_"))
async def wd_no(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("No access", show_alert=True)

    wid = int(call.data.split("_")[2])
    pool = await get_pool()

    data = await pool.fetchrow("""
        SELECT user_id, amount, status
        FROM withdraws
        WHERE id=$1
    """, wid)

    if not data:
        return await call.answer("Withdraw tidak ditemukan")

    if data["status"] != "pending":
        return await call.answer("Sudah diproses")

    await pool.execute("""
        UPDATE users
        SET balance = balance + $1
        WHERE telegram_id = $2
    """, data["amount"], data["user_id"])

    await pool.execute("""
        UPDATE withdraws
        SET status='rejected'
        WHERE id=$1
    """, wid)

    try:
        await call.bot.send_message(
            data["user_id"],
            f"❌ Withdraw Rp{data['amount']:,} ditolak.\n💰 Saldo dikembalikan."
        )
    except:
        pass

    await call.answer("❌ Rejected")
    await call.message.delete()
