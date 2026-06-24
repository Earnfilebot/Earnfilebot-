from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


@router.callback_query(F.data == "vvip")
async def vvip_handler(call: CallbackQuery):

    msg = await call.message.edit_text("⏳ Loading VVIP...")

    text = (
        "💎 <b>VVIP ACCESS</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "🔥 <b>Welcome VVIP User</b>\n\n"
        "📌 <b>Manfaat Join VVIP Group:</b>\n"
        "━━━━━━━━━━━━━━\n"
        "✅ Update code setiap hari\n"
        "✅ Full notifikasi bot code terbaru\n"
        "✅ Akses fitur premium lebih cepat\n"
        "✅ Garansi support sampai paham\n"
        "✅ Dibimbing oleh admin jika tidak mengerti\n"
        "✅ Akses fitur eksklusif VVIP\n\n"
        "💎 Join VVIP = akses lebih stabil & prioritas\n\n"
        "━━━━━━━━━━━━━━"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 VVIP ACCESS NOW",
                    callback_data="vvip_join"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Kembali",
                    callback_data="account"
                )
            ]
        ]
    )

    await msg.edit_text(text, reply_markup=kb)
    await call.answer()
