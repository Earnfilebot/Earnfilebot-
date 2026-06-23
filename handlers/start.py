import asyncio
import logging
import json

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InputMediaDocument
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.force_sub import check_force_sub
from keyboards.menu import home_kb
from keyboards.join import join_kb
from database import get_pool

router = Router()


# =========================
# START (NORMAL + DEEP LINK)
# =========================
@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):

    await state.clear()

    args = message.text.split(maxsplit=1)

    # =========================
    # HANDLE DEEP LINK FILE
    # =========================
    if len(args) > 1:

        payload = args[1]

        if payload.startswith("getFile_"):

            code = payload.replace("getFile_", "")

            pool = await get_pool()

            file = await pool.fetchrow(
                "SELECT media FROM files WHERE code=$1",
                code
            )

            if not file:
                return await message.answer("❌ File tidak ditemukan")

            media = json.loads(file["media"])

            if not media:
                return await message.answer("❌ File kosong")

            first = media[0]

            fid = first.get("file_id")
            ftype = (first.get("type") or "document").lower()

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📂 OPEN PAGE",
                            callback_data=f"page:{code}:1"
                        )
                    ]
                ]
            )

            caption = (
                "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n"
                f"🔑 CODE: {code}\n"
                f"📦 FILE: {len(media)}\n"
                "━━━━━━━━━━━━━━"
            )

            try:
                if ftype == "photo":
                    await message.answer_photo(fid, caption=caption, reply_markup=keyboard)

                elif ftype == "video":
                    await message.answer_video(fid, caption=caption, reply_markup=keyboard)

                else:
                    await message.answer_document(fid, caption=caption, reply_markup=keyboard)

            except Exception as e:
                await message.answer(f"❌ ERROR MEDIA: {e}")

            return
    # =========================
    # NORMAL START
    # =========================
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"

    loading = await message.answer("⚡ Loading...")

    try:
        await process_start(message, loading, user_id, username)
    except Exception as e:
        logging.exception(f"START ERROR: {e}")
        await loading.edit_text("❌ SYSTEM ERROR START")


# =========================
# PROCESS START
# =========================
async def process_start(message, loading, user_id, username):

    bot = message.bot

    try:
        sub = await check_force_sub(bot, user_id)
    except Exception:
        sub = True

    if not sub:
        return await loading.edit_text(
            "❌ JOIN REQUIRED\n\nSilakan join semua channel",
            reply_markup=join_kb()
        )

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


# =========================
# HOME UI
# =========================
async def render_home_fast(bot, message, user_id):

    text = (
        "<b>📂 DECODER FILE BOT</b>\n\n"
        "Selamat datang di Decoder File Bot.\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID : <code>{user_id}</code>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Silakan pilih menu di bawah."
    )

    try:
        await message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=home_kb()
        )
    except Exception:
        await bot.send_message(
            user_id,
            text,
            parse_mode="HTML",
            reply_markup=home_kb()
        )


# =========================
# CALLBACK HOME
# =========================
@router.callback_query(F.data == "home")
async def back_home(call: CallbackQuery, state: FSMContext):

    await state.clear()

    user_id = call.from_user.id

    try:
        ok = await check_force_sub(call.bot, user_id)
    except Exception:
        ok = True

    if not ok:
        await call.message.answer(
            "❌ JOIN REQUIRED",
            reply_markup=join_kb()
        )
        return await call.answer()

    await render_home_fast(call.bot, call.message, user_id)
    await call.answer()
