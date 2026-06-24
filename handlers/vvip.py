from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


@router.callback_query(F.data == "vvip")
async def vvip_handler(call: CallbackQuery):

    msg = await call.message.edit_text("⏳ Loading VVIP...")

    text = (
        "💎 <b>VVIP ACCESS</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "🔥 Welcome VVIP User\n"
        "✨ Fitur eksklusif akan ditambahkan\n\n"
        "━━━━━━━━━━━━━━"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔙 Kembali", callback_data="account")
            ]
        ]
    )

    await msg.edit_text(text, reply_markup=kb)
    await call.answer()
