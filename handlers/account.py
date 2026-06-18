from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_pool

router = Router()


def rupiah(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except:
        return "0"


async def loading(call: CallbackQuery):
    return await call.message.edit_text("⏳ Loading...")


# =========================
# ACCOUNT DASHBOARD
# =========================
@router.callback_query(F.data == "account")
async def account_handler(call: CallbackQuery):

    msg = await loading(call)

    user_id = call.from_user.id
    pool = await get_pool()

    user = await pool.fetchrow(
        "SELECT balance FROM users WHERE telegram_id=$1",
        user_id
    )

    balance = user["balance"] if user else 0

    total_tx = await pool.fetchval(
        "SELECT COUNT(*) FROM transactions WHERE user_id=$1",
        user_id
    ) or 0

    total_income = await pool.fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=$1",
        user_id
    ) or 0

    hot = await pool.fetch(
        """
        SELECT code, COUNT(*) AS sold
        FROM transactions
        WHERE code IS NOT NULL
        GROUP BY code
        ORDER BY sold DESC
        LIMIT 5
        """
    )

    hot_text = "\n".join(
        [f"{i}. <code>{h['code']}</code> — {h['sold']}x"
         for i, h in enumerate(hot, 1)]
    ) if hot else "❌ Belum ada data"

    text = (
        "━━━━━━━━━━━━━━\n"
        "💼 <b>ACCOUNT DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"👤 User ID   : <code>{user_id}</code>\n"
        f"💰 Balance   : <b>Rp {rupiah(balance)}</b>\n"
        f"📦 Orders    : <b>{total_tx}</b>\n"
        f"💸 Income    : <b>Rp {rupiah(total_income)}</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "🔥 <b>HOT PRODUCT</b>\n"
        f"{hot_text}\n"
        "━━━━━━━━━━━━━━"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Refresh", callback_data="account")
            ],
            [
                InlineKeyboardButton(text="📜 History", callback_data="trx"),
                InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw")
            ],
            [
                InlineKeyboardButton(text="🆓 FREE CODE", callback_data="free_code"),
                InlineKeyboardButton(text="💎 PAID CODE", callback_data="paid_code")
            ],
            [
                InlineKeyboardButton(text="🏆 Top Product", callback_data="top_product")
            ],
            [
                InlineKeyboardButton(text="🏠 Home", callback_data="home")
            ]
        ]
    )

    await msg.edit_text(text, reply_markup=kb)
    await call.answer()


# =========================
# FREE CODE LIST
# =========================
@router.callback_query(F.data == "free_code")
async def free_code(call: CallbackQuery):

    msg = await loading(call)
    pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT code, amount, created_at
        FROM transactions
        WHERE status IS NULL OR status='free'
        ORDER BY id DESC
        LIMIT 10
        """
    )

    text = "🆓 <b>FREE CODE</b>\n━━━━━━━━━━━━━━\n\n"

    if not rows:
        text += "❌ Tidak ada data"
    else:
        for r in rows:
            text += (
                f"📦 <code>{r['code']}</code>\n"
                f"💰 Rp {rupiah(r['amount'])}\n"
                "━━━━━━━━━━━━━━\n"
            )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="account")]
        ]
    )

    await msg.edit_text(text, reply_markup=kb)
    await call.answer()


# =========================
# PAID CODE LIST
# =========================
@router.callback_query(F.data == "paid_code")
async def paid_code(call: CallbackQuery):

    msg = await loading(call)
    pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT code, amount, created_at
        FROM transactions
        WHERE status='paid'
        ORDER BY id DESC
        LIMIT 10
        """
    )

    text = "💎 <b>PAID CODE</b>\n━━━━━━━━━━━━━━\n\n"

    if not rows:
        text += "❌ Tidak ada data"
    else:
        for r in rows:
            text += (
                f"📦 <code>{r['code']}</code>\n"
                f"💰 Rp {rupiah(r['amount'])}\n"
                "━━━━━━━━━━━━━━\n"
            )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="account")]
        ]
    )

    await msg.edit_text(text, reply_markup=kb)
    await call.answer()
