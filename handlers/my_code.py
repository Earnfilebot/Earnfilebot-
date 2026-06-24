from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_pool

router = Router()


@router.callback_query(F.data == "my_code")
async def my_code(call: CallbackQuery):

    msg = await call.message.edit_text("⏳ Loading...")

    pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT code
        FROM transactions
        WHERE user_id = $1
        AND code IS NOT NULL
        ORDER BY id DESC
        """,
        call.from_user.id
    )

    text = "📦 <b>MY CODE</b>\n━━━━━━━━━━━━━━\n\n"

    if not rows:
        text += "❌ Belum ada code."
    else:
        for i, row in enumerate(rows, 1):
            text += f"{i}. <code>{row['code']}</code>\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Kembali", callback_data="account")]
        ]
    )

    await msg.edit_text(text, reply_markup=kb)
    await call.answer()
