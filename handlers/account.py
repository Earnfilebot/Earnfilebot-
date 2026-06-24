from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


async def loading(call: CallbackQuery):
    return await call.message.edit_text("⏳ Loading...")


@router.callback_query(F.data == "account")
async def account_handler(call: CallbackQuery):

    msg = await loading(call)

    user_id = call.from_user.id

    text = (
        "━━━━━━━━━━━━━━\n"
        "👤 <b>ACCOUNT INFO</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🆔 User ID : <code>{user_id}</code>\n"
        "📊 Status : ✅ Akun Fresh & Aman\n\n"
        "━━━━━━━━━━━━━━"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📦 My Code", callback_data="my_code")
            ],
            [
                InlineKeyboardButton(text="💎 VVIP", callback_data="vvip")
            ],
            [
                InlineKeyboardButton(text="🔙 Kembali", callback_data="home")
            ]
        ]
    )

    await msg.edit_text(text, reply_markup=kb)
    await call.answer()
