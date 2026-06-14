from aiogram import Router, F
from aiogram.types import CallbackQuery

from utils.force_sub import check_force_sub
from keyboards.menu import home_kb

router = Router()


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(
    call: CallbackQuery
):

    if not await check_force_sub(
        call.bot,
        call.from_user.id
    ):
        await call.answer(
            "❌ Kamu belum join semua channel.",
            show_alert=True
        )
        return

    text = f"""
EARNFILEBOT

🆔 ID : {call.from_user.id}
💰 SALDO : Rp0

ᶜᵒᵖʸʳⁱᵍʰᵗ ᵒᶠ ᴱᵃʳⁿᶠⁱˡᵉᴮᵒᵗ
"""

    await call.message.edit_text(
        text,
        reply_markup=home_kb()
    )
