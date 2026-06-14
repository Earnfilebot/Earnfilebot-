from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from utils.force_sub import check_force_sub
from keyboards.menu import home_kb
from keyboards.join import join_kb
from database import get_pool

from utils.ui_manager import set_ui, USER_UI

router = Router()


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):

    # 🔥 RESET STATE (anti upfile nyangkut)
    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username
    bot = message.bot

    # =========================
    # FORCE SUB CHECK
    # =========================
    if not await check_force_sub(bot, user_id):
        await message.answer(
            "❌ Kamu belum join semua channel.\n\nSilakan join dulu lalu klik CHECK.",
            reply_markup=join_kb()
        )
        return

    # =========================
    # DATABASE USER
    # =========================
    pool = await get_pool()

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

    user = await pool.fetchrow(
        "SELECT balance FROM users WHERE telegram_id = $1",
        user_id
    )

    balance = user["balance"] if user and user["balance"] is not None else 0

    # =========================
    # CLEAN HOME UI TEXT
    # =========================
    text = f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

🆔 𝗜𝗗 : {user_id}
💰 𝗕𝗔𝗟𝗔𝗡𝗖𝗘 : Rp{balance}

────────────────
𝗖𝗢𝗣𝗬𝗥𝗜𝗚𝗛𝗧 𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫
"""

    # =========================
    # UI MANAGER (AUTO REPLACE SYSTEM)
    # =========================
    ui = USER_UI.get(user_id)

    if ui:
        try:
            await bot.edit_message_text(
                chat_id=ui["chat_id"],
                message_id=ui["message_id"],
                text=text,
                reply_markup=home_kb()
            )
            return
        except:
            # kalau gagal, reset UI
            USER_UI.pop(user_id, None)

    # =========================
    # FIRST TIME UI CREATE
    # =========================
    msg = await message.answer(
        text,
        reply_markup=home_kb()
    )

    await set_ui(user_id, msg.chat.id, msg.message_id)
