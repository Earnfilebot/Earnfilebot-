from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards.menu import home_kb

router = Router()

@router.message(CommandStart())
async def start_cmd(message: Message):

    text = f"""
EARNFILEBOT

🆔 ID : {message.from_user.id}
💰 SALDO : Rp0

ᶜᵒᵖʸʳⁱᵍʰᵗ ᵒᶠ ᴱᵃʳⁿᶠⁱˡᵉᴮᵒᵗ
"""

    await message.answer(
        text,
        reply_markup=home_kb()
    )
