import asyncio
import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from utils.force_sub import check_force_sub
from keyboards.menu import home_kb
from keyboards.join import join_kb
from database import get_pool

router = Router()


def rupiah(amount):
    try:
        return f"{int(amount):,}".replace(",", ".")
    except:
        return "0"


# =========================
# START
# =========================
@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):

    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username or "unknown"

    try:
        loading = await message.answer("⚡ Loading...")
    except Exception as e:
        logging.exception(f"FAILED SEND LOADING: {e}")
        return

    try:
        await process_start(message, loading, user_id, username)
    except Exception as e:
        logging.exception(f"START ERROR: {e}")
        try:
            await loading.edit_text("❌ SYSTEM ERROR START")
        except Exception as e2:
            logging.warning(f"FAILED EDIT ERROR MSG: {e2}")


# =========================
# PROCESS START
# =========================
async def process_start(message, loading, user_id, username):

    bot = message.bot

    try:
        logging.info(f"START PROCESS | USER: {user_id}")

        # FORCE SUB CHECK
        try:
            sub = await check_force_sub(bot, user_id)
            logging.info(f"FORCE SUB RESULT: {sub}")
        except Exception as e:
            logging.exception(f"FORCE SUB ERROR: {e}")
            sub = True  # fallback biar tidak block user

        if not sub:
            try:
                await loading.edit_text(
                    "❌ JOIN REQUIRED\n\nSilakan join semua channel",
                    reply_markup=join_kb()
                )
            except Exception as e:
                logging.warning(f"EDIT JOIN FAIL: {e}")
            return

        pool = await get_pool()

        await pool.execute(
            """
            INSERT INTO users (telegram_id, username)
            VALUES ($1, $2)
            ON CONFLICT (telegram_id) DO NOTHING
            """,
            user_id,
            username
        )

        await render_home_fast(bot, loading, user_id)

    except Exception as e:
        logging.exception(f"PROCESS START ERROR: {e}")
        try:
            await loading.edit_text("❌ SYSTEM ERROR")
        except Exception as e2:
            logging.warning(f"FAILED EDIT ERROR: {e2}")


# =========================
# HOME
# =========================
async def render_home_fast(bot, message, user_id):

    logging.info("➡️ ENTER render_home_fast")

    try:

        text = (
            "<b>📂 DECODER FILE BOT</b>\n\n"
            "Selamat datang di Decoder File Bot.\n"
            "Bot ini digunakan untuk membuka, membaca, dan mendekode file yang didukung.\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID : <code>{user_id}</code>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "Silakan pilih menu di bawah."
        )

        try:
            logging.info("➡️ TRY EDIT MESSAGE")

            await message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=home_kb()
            )

            logging.info("✅ EDIT SUCCESS")

        except Exception as e:
            logging.warning(f"EDIT FAIL: {e}")

            await bot.send_message(
                user_id,
                text,
                parse_mode="HTML",
                reply_markup=home_kb()
            )

    except Exception as e:
        logging.exception(f"HOME ERROR: {e}")
# =========================
# CALLBACK HOME
# =========================
@router.callback_query(F.data == "home")
async def back_home(call: CallbackQuery, state: FSMContext):

    await state.clear()

    user_id = call.from_user.id

    try:
        ok = await check_force_sub(call.bot, user_id)
    except Exception as e:
        logging.exception(f"FORCE SUB CALLBACK ERROR: {e}")
        ok = True

    if not ok:
        try:
            await call.message.answer(
                "❌ JOIN REQUIRED",
                reply_markup=join_kb()
            )
        except Exception as e:
            logging.warning(f"JOIN MSG FAIL: {e}")

        return await call.answer()

    await render_home_fast(call.bot, call.message, user_id)

    await call.answer()
