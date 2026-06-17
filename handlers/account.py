from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data == "account")
async def account(call: CallbackQuery):

    user_id = call.from_user.id

    text = (
        "👤 ACCOUNT INFO\n"
        f"ID: {user_id}\n\n"
        "⚠️ BOT SEDANG DALAM PENGEMBANGAN\n"
        "Silahkan cek kembali suatu saat."
    )

    await call.message.edit_text(text)
    await call.answer("ℹ️ Feature in development", show_alert=True)
