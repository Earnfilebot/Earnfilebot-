from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from utils.force_sub import check_force_sub
from keyboards.menu import home_kb
from keyboards.join import join_kb
from database import get_pool

from utils.ui_manager import set_ui, USER_UI

router = Router()


# =========================
# RENDER HOME (CORE UI)
# =========================
async def render_home(bot, message, user_id, username):

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

    balance = user["balance"] if user and user["balance"] else 0

    # =========================
    # CLEAN FONT (CONSISTENT)
    # =========================
    text = (
        "EARNFILEBOX\n\n"
        "HOME DASHBOARD\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"ID : {user_id}\n"
        f"BALANCE : Rp{balance}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

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
            USER_UI.pop(user_id, None)

    msg = await message.answer(text, reply_markup=home_kb())
    await set_ui(user_id, msg.chat.id, msg.message_id)


# =========================
# START COMMAND
# =========================
@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):

    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    bot = message.bot

    # FORCE SUB
    if not await check_force_sub(bot, user_id):
        await message.answer(
            "EARNFILEBOX\n\n"
            "STATUS : JOIN REQUIRED\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Silakan join semua channel terlebih dahulu",
            reply_markup=join_kb()
        )
        return

    await render_home(bot, message, user_id, username)


# =========================
# HOME BUTTON
# =========================
@router.callback_query(F.data == "home")
async def back_home(call: CallbackQuery, state: FSMContext):

    await state.clear()

    user_id = call.from_user.id
    username = call.from_user.username or "unknown"

    await render_home(call.bot, call.message, user_id, username)

    await call.answer()
