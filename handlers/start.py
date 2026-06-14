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

    # FORCE SUB
    if not await check_force_sub(message.bot, user_id):
        await message.answer(
            "❌ Kamu belum join semua channel.\n\nSilakan join dulu lalu klik CHECK.",
            reply_markup=join_kb()
        )
        return

    pool = await get_pool()

    # SAVE USER (lebih aman pakai INSERT ON CONFLICT)
    await pool.execute(
        """
        INSERT INTO users (telegram_id, username)
        VALUES ($1, $2)
        ON CONFLICT (telegram_id) DO UPDATE
        SET username = EXCLUDED.username
        """,
        user_id,
        username
    )

    # AMBIL SALDO (aman kalau null)
    user = await pool.fetchrow(
        "SELECT balance FROM users WHERE telegram_id = $1",
        user_id
    )

    balance = user["balance"] if user and user["balance"] is not None else 0

    text = f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧

🆔 𝗜𝗗 : {user_id}
💰 𝗕𝗔𝗟𝗔𝗡𝗖𝗘 : Rp{balance}

────────────────
𝗖𝗢𝗣𝗬𝗥𝗜𝗚𝗛𝗧 𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧
"""

    await message.answer(
        text,
        reply_markup=home_kb()
    )
