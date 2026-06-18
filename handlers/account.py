from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_pool

router = Router()


# =========================
# FORMAT RUPIAH
# =========================
def rupiah(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except:
        return "0"


# =========================
# ACCOUNT DASHBOARD
# =========================
@router.callback_query(F.data == "account")
async def account_handler(call: CallbackQuery):

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

    # =========================
    # HOT PRODUCT
    # =========================
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

    hot_text = ""
    if hot:
        for i, h in enumerate(hot, 1):
            hot_text += f"{i}. <code>{h['code']}</code> — {h['sold']}x\n"
    else:
        hot_text = "❌ Belum ada data"

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
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="account")],
            [
                InlineKeyboardButton(text="📜 History", callback_data="trx"),
                InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw")
            ],
            [
                InlineKeyboardButton(text="🏆 Top Product", callback_data="top_product")
            ],
            [
                InlineKeyboardButton(text="🏠 Home", callback_data="home")
            ]
        ]
    )

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# =========================
# TRANSACTION HISTORY
# =========================
@router.callback_query(F.data == "trx")
async def transaction_history(call: CallbackQuery):

    user_id = call.from_user.id
    pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT code, amount, status, created_at
        FROM transactions
        WHERE user_id=$1
        ORDER BY id DESC
        LIMIT 10
        """,
        user_id
    )

    if not rows:
        return await call.message.edit_text(
            "📜 <b>TRANSACTION HISTORY</b>\n\n❌ Belum ada transaksi",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Home", callback_data="account")]
                ]
            )
        )

    text = "📜 <b>TRANSACTION HISTORY</b>\n━━━━━━━━━━━━━━\n\n"

    for r in rows:
        status = "✅ PAID" if r["status"] == "paid" else "⏳ PENDING"
        created = r["created_at"]

        created_text = created.strftime("%d-%m-%Y %H:%M") if created else "-"

        text += (
            f"📦 <code>{r.get('code','-')}</code>\n"
            f"💰 Rp {rupiah(r.get('amount',0))}\n"
            f"📊 {status}\n"
            f"🕒 {created_text}\n"
            "━━━━━━━━━━━━━━\n"
        )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="account")]
        ]
    )

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# =========================
# TOP PRODUCT
# =========================
@router.callback_query(F.data == "top_product")
async def top_product(call: CallbackQuery):

    pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT code, COUNT(*) AS sold, COALESCE(SUM(amount),0) AS revenue
        FROM transactions
        WHERE code IS NOT NULL
        GROUP BY code
        ORDER BY sold DESC
        LIMIT 10
        """
    )

    if not rows:
        return await call.message.edit_text(
            "🏆 <b>TOP PRODUCT</b>\n\n❌ Belum ada data penjualan",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Back", callback_data="account")]
                ]
            )
        )

    text = "🏆 <b>TOP SELLING PRODUCT</b>\n━━━━━━━━━━━━━━\n\n"

    for i, r in enumerate(rows, 1):
        text += (
            f"{i}. <code>{r['code']}</code>\n"
            f"   🔥 Sold: {r['sold']}\n"
            f"   💰 Revenue: Rp {rupiah(r['revenue'])}\n"
            "━━━━━━━━━━━━━━\n"
        )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="account")]
        ]
    )

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()
