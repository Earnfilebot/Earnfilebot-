from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_pool

router = Router()


@router.callback_query(F.data == "account")
async def account_handler(call: CallbackQuery):

    await call.message.edit_text("⏳ Loading...")

    pool = await get_pool()
    user_id = call.from_user.id

    user = await pool.fetchrow(
        """
        SELECT vip, vip_until
        FROM users
        WHERE telegram_id=$1
        """,
        user_id
    )

    vip_status = "🆓 FREE"
    vip_type = "-"
    remaining = "-"
    duration = "-"

    if user and user["vip"] and user["vip_until"]:

        now = datetime.now(timezone.utc)
        vip_until = user["vip_until"]

        # samakan timezone biar aman
        if vip_until.tzinfo is None:
            vip_until = vip_until.replace(tzinfo=timezone.utc)
        else:
            vip_until = vip_until.astimezone(timezone.utc)

        if vip_until > now:

            delta = vip_until - now
            remaining_days = delta.days

            vip_status = "👑 VIP ACTIVE"

            if remaining_days <= 1:
                vip_type = "Harian"
            elif remaining_days <= 30:
                vip_type = "Bulanan"
            else:
                vip_type = "Lifetime"

            remaining = f"{remaining_days} hari"
            duration = f"{remaining_days} hari"

        else:
            vip_status = "❌ EXPIRED"
            vip_type = "-"
            remaining = "0 hari"
            duration = "0 hari"

    text = (
        "━━━━━━━━━━━━━━\n"
        "👤 <b>ACCOUNT INFO</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🆔 User ID : <code>{user_id}</code>\n"
        f"💎 Status : {vip_status}\n"
        f"📦 Tipe : {vip_type}\n"
        f"⏳ Sisa VIP : {remaining}\n"
        f"📊 Durasi VIP : {duration}\n\n"
        "━━━━━━━━━━━━━━"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 My Code", callback_data="my_code")],
            [InlineKeyboardButton(text="💎 VVIP", callback_data="vvip")],
            [InlineKeyboardButton(text="🔙 Kembali", callback_data="home")]
        ]
    )

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()
