from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data == "help")
async def help_menu(call: CallbackQuery):

    text = (
        "❓ HELP MENU\n\n"
        "📌 Cara pakai bot:\n"
        "1. Klik GET FILE\n"
        "2. Masukkan kode file\n"
        "3. Jika berbayar, lakukan pembayaran\n"
        "4. File akan terbuka otomatis\n\n"
        "⚠️ BEBERAPA FITUR MASIH DALAM PENGEMBANGAN\n"
        "Silahkan cek kembali secara berkala."
    )

    await call.message.edit_text(text)
    await call.answer("ℹ️ Help opened", show_alert=True)
