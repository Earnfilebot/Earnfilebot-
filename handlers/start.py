from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from utils.force_sub import check_force_sub
from keyboards.menu import home_kb
from keyboards.join import join_kb
from database import get_pool

router = Router()


@router.message(CommandStart())
async def start_cmd(message: Message):

    user_id = message.from_user.id
    username = message.from_user.username

    # Force Subscribe
    if not await check_force_sub(
        message.bot,
        user_id
    ):
        await message.answer(
            "❌ Join semua channel terlebih dahulu.",
            reply_markup=join_kb()
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
        user_id,
        username
    )

    # Ambil saldo dari DB
    user = await pool.fetchrow(
        "SELECT balance FROM users WHERE telegram_id = $1",
        user_id
    )

    balance = user["balance"] if user else 0

    text = f"""
EARNFILEBOT

🆔 ID : {user_id}
💰 SALDO : Rp{balance}

ᶜᵒᵖʸʳⁱᵍʰᵗ ᵒᶠ ᴱᵃʳⁿᶠⁱˡᵉᴮᵒᵗ
"""

    await message.answer(
        text,
        reply_markup=home_kb()
    )
