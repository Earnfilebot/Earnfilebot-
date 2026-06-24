from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):

    text = (
        "━━━━━━━━━━━━━━\n"
        "ℹ️ <b>ABOUT BOT</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "🤖 <b>Name</b>    : EarnFileBox Bot\n"
        "⚙️ <b>Version</b> : 1.0 (MVP Release)\n"
        "📦 <b>Type</b>    : File & Code Management Bot\n\n"
        "━━━━━━━━━━━━━━\n"
        "💡 <b>DESKRIPSI</b>\n"
        "Bot ini digunakan untuk mengelola file dan code digital\n"
        "dengan sistem upload, akses, dan pengambilan otomatis.\n\n"
        "━━━━━━━━━━━━━━\n"
        "🚀 <b>FITUR UTAMA</b>\n"
        "• Upload file & code\n"
        "• Decode / akses file\n"
        "• Sistem akun user\n"
        "• My Code system\n"
        "• VVIP access system\n\n"
        "━━━━━━━━━━━━━━\n"
        "🛠 <b>STATUS</b>\n"
        "Masih dalam tahap pengembangan aktif menuju versi stabil.\n"
        "Fitur akan terus diperbarui secara berkala.\n\n"
        "━━━━━━━━━━━━━━\n"
        "🇮🇩 <b>DEVELOPED BY</b>\n"
        "Dikembangkan oleh remaja Indonesia 🇮🇩\n"
        "sebagai project pembelajaran sistem bot automation.\n\n"
        "━━━━━━━━━━━━━━\n"
        "🔥 <b>GOAL</b>\n"
        "Membuat sistem bot sederhana, cepat, dan mudah digunakan."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏠 Home", callback_data="home"),
                InlineKeyboardButton(text="👤 Account", callback_data="account")
            ]
        ]
    )

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()
