from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from utils.force_sub import check_force_sub
from keyboards.menu import home_kb
from database import get_pool

router = Router()


@router.message(CommandStart())
async def start_cmd(message: Message):

    # Force Subscribe
    if not await check_force_sub(
        message.bot,
        message.from_user.id
    ):
        await message.answer(
            "❌ Join semua channel terlebih dahulu."
        )
        return

    # Save User
    pool = await get_pool()

    await pool.execute(
        """
        INSERT INTO users (
            telegram_id,
            username
        )
        VALUES ($1, $2)
        ON CONFLICT (telegram_id)
        DO NOTHING
        """,
        message.from_user.id,
        message.from_user.username
    )

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
