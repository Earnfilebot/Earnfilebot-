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

    # =========================
    # USER BALANCE
    # =========================
    user = await pool.fetchrow(
        "SELECT balance FROM users WHERE telegram_id=$1",
        user_id
    )

    balance = user["balance"] if user else 0

    # =========================
    # TOTAL TRANSACTIONS
    # =========================
    total_tx = await pool.fetchval(
        "SELECT COUNT(*) FROM transactions WHERE user_id=$1",
        user_id
    ) or 0

    # =========================
    # TOTAL INCOME (SAFE)
    # =========================
    total_income = await pool.fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=$1",
        user_id
    ) or 0

    # =========================
    # HOT PRODUCT (SAFE GROUP BY)
    # =========================
    hot = await pool.fetch(
        """
        SELECT COALESCE(code,'UNKNOWN') AS code, COUNT(*) AS total
        FROM transactions
        WHERE code IS NOT NULL
        GROUP BY code
        ORDER BY total DESC
        LIMIT 3
        """
    )

    hot_text = "\n".join(
        [f"🔥 {h['code']} — {h['total']} sold" for h in hot]
    ) if hot else "Belum ada data"

    # =========================
    # TEXT UI
    # =========================
    text = (
        "╭━━━ 💼 ACCOUNT DASHBOARD ━━━╮\n\n"
        f"👤 ID USER   : <code>{user_id}</code>\n"
        f"💰 BALANCE   : <b>Rp {rupiah(balance)}</b>\n"
        f"📦 PURCHASE  : <b>{total_tx}</b>\n"
        f"💸 INCOME    : <b>Rp {rupiah(total_income)}</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "🔥 HOT PRODUCT:\n"
        f"{hot_text}\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )

    # =========================
    # KEYBOARD (AIROGRAM V3 FIXED)
    # =========================
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 REFRESH", callback_data="account")
            ],
            [
                InlineKeyboardButton(text="📜 TRANSACTIONS", callback_data="trx"),
                InlineKeyboardButton(text="💸 WITHDRAW", callback_data="withdraw")
            ],
            [
                InlineKeyboardButton(text="🏆 TOP PRODUCT", callback_data="top_product")
            ],
            [
                InlineKeyboardButton(text="🏠 HOME", callback_data="home")
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

    pool = await get_pool()
    user_id = call.from_user.id

    rows = await pool.fetch(
        """
        SELECT code, amount, status, created_at
        FROM transactions
        WHERE user_id=$1
        ORDER BY id DESC
        LIMIT 5
        """,
        user_id
    )

    if not rows:
        return await call.message.edit_text(
            "📜 TRANSAKSI\n\n❌ Belum ada transaksi",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 HOME", callback_data="home")]
                ]
            )
        )

    text = "📜 TRANSACTION HISTORY\n\n"

    for r in rows:
        status = "✅ PAID" if r["status"] == "paid" else "⏳ PENDING"

        created = r["created_at"]
        created_text = created.strftime("%d-%m-%Y %H:%M") if created else "-"

        text += (
            f"📦 {r.get('code','-')}\n"
            f"💰 Rp {rupiah(r.get('amount',0))}\n"
            f"📊 {status}\n"
            f"🕒 {created_text}\n"
            "━━━━━━━━━━━━━━\n"
        )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 BACK", callback_data="account")]
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
        SELECT COALESCE(code,'UNKNOWN') AS code,
               COUNT(*) AS sold,
               COALESCE(SUM(amount),0) AS revenue
        FROM transactions
        WHERE code IS NOT NULL
        GROUP BY code
        ORDER BY sold DESC
        LIMIT 10
        """
    )

    if not rows:
        return await call.message.edit_text(
            "🏆 TOP PRODUCT\n\n❌ Belum ada data",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 BACK", callback_data="account")]
                ]
            )
        )

    text = "🏆 TOP SELLING PRODUCT\n\n"

    for r in rows:
        text += (
            f"📦 {r['code']}\n"
            f"🔥 Sold: {r['sold']}\n"
            f"💰 Revenue: Rp {rupiah(r['revenue'])}\n"
            "━━━━━━━━━━━━━━\n"
        )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 BACK", callback_data="account")]
        ]
    )

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()
