from aiogram import Router, F
from aiogram.types import CallbackQuery

from utils.force_sub import check_force_sub
from keyboards.join import join_kb
from handlers.start import render_home_fast

router = Router()


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery):

    user_id = call.from_user.id

    if not await check_force_sub(
        call.bot,
        user_id
    ):

        await call.answer(
            "❌ Kamu belum join semua channel.",
            show_alert=True
        )

        try:
            await call.message.edit_text(
                "❌ Kamu belum join semua channel.\n\n"
                "Silakan join dulu lalu klik CHECK lagi.",
                reply_markup=join_kb()
            )
        except:
            pass

        return

    await render_home_fast(
        call.bot,
        call.message,
        user_id,
    )

    await call.answer("✅ Verifikasi berhasil")
