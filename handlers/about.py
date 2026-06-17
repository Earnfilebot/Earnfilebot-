from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):

    text = (
        "ℹ️ ABOUT BOT\n\n"
        "🤖 Nama: Earn File Box Bot\n"
        "⚙️ Version: 1.0\n"
        "📦 Type: Decoder Earn File System\n\n"
        "🔥 Feature:\n"
        "- Buy & unlock file\n"
        "- QRIS payment\n"
        "- Auto access system\n\n"
        "⚠️ BOT MASIH DALAM PENGEMBANGAN\n"
        "Beberapa fitur mungkin belum stabil."
    )

    await call.message.edit_text(text)
    await call.answer("ℹ️ About opened", show_alert=True)
