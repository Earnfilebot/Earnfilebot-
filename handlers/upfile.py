import asyncio
import json
import random
import string
import time
import re

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import CHANNEL_ID
from database import get_pool
from utils.force_sub import check_force_sub
from keyboards.join import join_kb

router = Router()

# =========================
# CONFIG
# =========================
MAX_MEDIA = 200
UPDATE_DELAY = 0.3

_last_update = {}
_user_locks = {}

def get_lock(user_id: int):
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


# =========================
# SAFE EDIT
# =========================
async def safe_update(bot, chat_id, message_id, text, user_id):
    now = time.time()
    last = _last_update.get(user_id, 0)

    if now - last < UPDATE_DELAY:
        await asyncio.sleep(UPDATE_DELAY)

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text
        )
        _last_update[user_id] = time.time()
    except:
        pass


# =========================
# STATE
# =========================
class UploadState(StatesGroup):
    upload = State()
    wait_price = State()


# =========================
# START
# =========================
@router.callback_query(F.data == "upfile")
async def start_upfile(call: CallbackQuery, state: FSMContext):

    await call.answer()
    async with get_lock(call.from_user.id):

        await state.clear()

        if not await check_force_sub(call.bot, call.from_user.id):
            return await call.message.answer(
                "❌ Join channel dulu",
                reply_markup=join_kb()
            )

        msg = await call.message.edit_text("⏳ Loading...")
        await asyncio.sleep(0.2)

        msg = await msg.edit_text(
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n📤 SEND MEDIA NOW"
        )

        await state.update_data(
            upload_mode=True,
            media=[],
            progress_msg_id=msg.message_id,
            saving=False,
            finalizing=False
        )


# =========================
# RECEIVE MEDIA
# =========================
@router.message(F.document | F.video | F.photo)
async def receive_media(message: Message, state: FSMContext):

    async with get_lock(message.from_user.id):

        data = await state.get_data()

        if not data.get("upload_mode"):
            return

        media = data.get("media", [])

        if len(media) >= MAX_MEDIA:
            return await message.answer("❌ Maks 200 file")

        if message.document:
            fid = message.document.file_id
            ftype = "document"
        elif message.video:
            fid = message.video.file_id
            ftype = "video"
        else:
            fid = message.photo[-1].file_id
            ftype = "photo"

        media.append({"file_id": fid, "type": ftype})
        await state.update_data(media=media)

        try:
            await message.delete()
        except:
            pass

        data = await state.get_data()
        msg_id = data.get("progress_msg_id")

        # =========================
        # CREATE PROGRESS ONCE + BUTTONS FIX
        # =========================
        if not msg_id:

            kb = InlineKeyboardBuilder()
            kb.button(text="⏹ STOP & SAVE", callback_data="save_upfile")
            kb.button(text="❌ CANCEL", callback_data="cancel_upfile")
            kb.adjust(2)

            progress = await message.answer(
                "📦 UPLOADING...\n[░░░░░░░░░░]\n0/200",
                reply_markup=kb.as_markup()
            )

            msg_id = progress.message_id
            await state.update_data(progress_msg_id=msg_id)

        # =========================
        # UPDATE PROGRESS
        # =========================
        total = len(media)
        bar = "█" * int(total / MAX_MEDIA * 10) + "░" * (10 - int(total / MAX_MEDIA * 10))

        text = f"📦 UPLOADING...\n[{bar}]\n{total}/{MAX_MEDIA}\n✅ accepted"

        await safe_update(message.bot, message.chat.id, msg_id, text, message.from_user.id)


# =========================
# CANCEL
# =========================
@router.callback_query(F.data == "cancel_upfile")
async def cancel(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()
    msg_id = data.get("progress_msg_id")

    await state.clear()

    try:
        if msg_id:
            await call.bot.delete_message(call.message.chat.id, msg_id)
    except:
        pass

    await call.message.edit_text("❌ CANCELLED")


# =========================
# SAVE → TYPE (FREE / PAID FIX)
# =========================
@router.callback_query(F.data == "save_upfile")
async def choose_type(call: CallbackQuery, state: FSMContext):

    await call.answer()
    data = await state.get_data()

    if not data.get("media"):
        return await call.answer("No media", show_alert=True)

    kb = InlineKeyboardBuilder()
    kb.button(text="🆓 FREE", callback_data="type_free")
    kb.button(text="💰 PAID", callback_data="type_paid")
    kb.adjust(2)

    await state.update_data(finalizing=True)

    await call.message.edit_text(
        "📦 PILIH TYPE",
        reply_markup=kb.as_markup()
    )


# =========================
# TYPE HANDLER
# =========================
@router.callback_query(F.data.startswith("type_"))
async def handle_type(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()
    choice = call.data.split("_")[1]

    if choice == "free":

        await state.update_data(
            file_type="free",
            is_paid=False,
            price=0
        )

        await call.message.edit_text("⏳ Saving...")
        await finalize_save(call.message, state)
        return

    await state.update_data(
        file_type="paid",
        is_paid=True
    )

    await state.set_state(UploadState.wait_price)
    await call.message.edit_text("💰 INPUT PRICE")


# =========================
# PRICE
# =========================
@router.message(UploadState.wait_price)
async def input_price(message: Message, state: FSMContext):

    cleaned = re.sub(r"[^0-9]", "", message.text or "")
    if not cleaned:
        return await message.answer("Invalid")

    price = int(cleaned)

    if price < 1000 or price > 100000:
        return await message.answer("Range 1000 - 100000")

    await state.update_data(price=price)

    try:
        await message.delete()
    except:
        pass

    await finalize_save(message, state)


# =========================
# FINAL SAVE
# =========================
async def finalize_save(message: Message, state: FSMContext):

    async with get_lock(message.from_user.id):

        data = await state.get_data()

        msg_id = data.get("progress_msg_id")
        try:
            if msg_id:
                await message.bot.delete_message(message.chat.id, msg_id)
        except:
            pass

        media = data.get("media", [])
        if not media:
            return

        file_type = data.get("file_type")
        is_paid = data.get("is_paid", False)
        price = data.get("price", 0)

        code = "EFB-" + "".join(random.choices(string.ascii_letters, k=12))

        await state.clear()

        text = (
            "💎 PREMIUM SAVED\n" if is_paid else "🎉 FREE SAVED\n"
        ) + f"\nCODE: `{code}`\nMEDIA: {len(media)}"

        await message.answer(text, parse_mode="Markdown")
