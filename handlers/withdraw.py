from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data == "withdraw")
async def withdraw(call: CallbackQuery):

    text = (
        "💸 WITHDRAW MENU\n\n"
        "⚠️ FITUR SEDANG DALAM PENGEMBANGAN\n"
        "Silahkan cek kembali suatu saat."
    )

    await call.message.edit_text(text)
    await call.answer("🚧 Under development", show_alert=True)
