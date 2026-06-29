import asyncio
import json
import random
import string
import time

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import CHANNEL_ID, BOT_URL
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
async def safe_update(bot, chat_id, message_id, text, user_id, reply_markup=None):
    if not message_id:
        return

    now = time.time()
    last = _last_update.get(user_id, 0)

    if now - last < UPDATE_DELAY:
        await asyncio.sleep(UPDATE_DELAY)

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup
        )
        _last_update[user_id] = time.time()

    except TelegramBadRequest:
        pass


# =========================
# STATE
# =========================
class UploadState(StatesGroup):
    upload = State()
    wait_folder = State()
    wait_expiry = State()
    wait_price = State()

# =========================
# START UPLOAD
# =========================
@router.callback_query(F.data == "upfile")
async def start_upfile(call: CallbackQuery, state: FSMContext):

    await call.answer()

    async with get_lock(call.from_user.id):

        await state.clear()
        await state.set_state(UploadState.upload)

        if not await check_force_sub(call.bot, call.from_user.id):
            return await call.message.answer(
                "❌ Join channel first",
                reply_markup=join_kb()
            )

        msg = await call.message.edit_text("⏳ Loading...")
        await asyncio.sleep(0.2)

        msg = await msg.edit_text(
            "📦 <b>UPLOAD MODE ACTIVE</b>\n\nSend your media now",
            parse_mode="HTML"
        )

        await state.update_data(
            upload_mode=True,
            media=[],
            share_media=True,
            progress_msg_id=msg.message_id,
            saving=False
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
            return await message.answer(f"❌ Max {MAX_MEDIA} files reached")

        if message.document:
            fid = message.document.file_id
        elif message.video:
            fid = message.video.file_id
        else:
            fid = message.photo[-1].file_id

        if any(x["file_id"] == fid for x in media):
            return

        media.append({"file_id": fid})
        await state.update_data(media=media)

        try:
            await message.delete()
        except:
            pass

        total = len(media)

        progress = min(10, int((total / MAX_MEDIA) * 10))
        bar = "█" * progress + "░" * (10 - progress)

        text = (
            "📦 <b>UPLOAD MANAGER</b>\n\n"
            f"📁 Total Files: <b>{total}</b>\n"
            f"📊 Progress: [{bar}]\n"
            f"{total}/{MAX_MEDIA}"
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="⏹ STOP & SAVE", callback_data="save_upfile")
        kb.button(text="❌ CANCEL", callback_data="cancel_upfile")
        kb.adjust(2)

        await safe_update(
            message.bot,
            message.chat.id,
            data.get("progress_msg_id"),
            text,
            message.from_user.id,
            kb.as_markup()
        )


# =========================
# CANCEL
# =========================
@router.callback_query(F.data == "cancel_upfile")
async def cancel(call: CallbackQuery, state: FSMContext):

    await call.answer()

    data = await state.get_data()
    msg_id = data.get("progress_msg_id")

    await state.clear()

    try:
        if msg_id:
            await call.bot.delete_message(call.message.chat.id, msg_id)
    except:
        pass

    await call.message.edit_text("❌ UPLOAD CANCELLED")


# =========================
# SAVE → SHARE MODE
# =========================
@router.callback_query(F.data == "save_upfile")
async def choose_share(call: CallbackQuery, state: FSMContext):

    await call.answer()

    data = await state.get_data()

    if data.get("saving"):
        return await call.answer("Processing...", show_alert=True)

    if not data.get("media"):
        return await call.answer("No media", show_alert=True)

    kb = InlineKeyboardBuilder()
    kb.button(text="🔗 SHARE MEDIA", callback_data="share_yes")
    kb.button(text="🔒 NO SHARE MEDIA", callback_data="share_no")
    kb.adjust(2)

    await call.message.edit_text(
        "📦 SELECT SHARE MODE",
        reply_markup=kb.as_markup()
    )


# =========================
# SHARE HANDLER → FOLDER NAME
# =========================
@router.callback_query(F.data.startswith("share_"))
async def handle_share(call: CallbackQuery, state: FSMContext):

    await call.answer()

    data = await state.get_data()

    share_media = call.data == "share_yes"

    await state.update_data(
        share_media=share_media,
        saving=False
    )

    await state.set_state(UploadState.wait_folder)

    await call.message.edit_text(
        "📝 ENTER FOLDER NAME\n\n"
        "Example:\n"
        "<code>My Anime Pack</code>\n\n"
        "Or send /skip for auto name",
        parse_mode="HTML"
    )


# =========================
# INPUT FOLDER
# =========================
@router.message(UploadState.wait_folder)
async def input_folder(message: Message, state: FSMContext):

    data = await state.get_data()

    text = message.text or ""

    if text.lower() == "/skip":
        folder_name = "Folder " + "".join(random.choices(string.ascii_uppercase, k=6))
    else:
        folder_name = text[:50]

    await state.update_data(folder_name=folder_name)

    kb = InlineKeyboardBuilder()
    kb.button(text="⏳ 1 Jam", callback_data="exp:3600")
    kb.button(text="⏳ 24 Jam", callback_data="exp:86400")
    kb.button(text="♾ Permanent", callback_data="exp:0")
    kb.adjust(1)

    await message.answer(
        "🕒 PILIH AUTO DELETE TIME",
        reply_markup=kb.as_markup()
    )

    await state.set_state(UploadState.wait_expiry)


# =========================
# EXPIRY SELECT
# =========================
@router.callback_query(F.data.startswith("exp:"))
async def set_expiry(call: CallbackQuery, state: FSMContext):

    await call.answer()

    expiry = int(call.data.split(":")[1])

    await state.update_data(expiry=expiry)

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🆓 Free",
        callback_data="file_free"
    )

    kb.button(
        text="💰 Paid",
        callback_data="file_paid"
    )

    kb.adjust(2)

    await call.message.edit_text(
        "💎 Pilih tipe file:",
        reply_markup=kb.as_markup()
    )

@router.callback_query(F.data == "file_paid")
async def file_paid(call: CallbackQuery, state: FSMContext):

    await call.answer()

    await call.message.edit_text(
        "💰 Masukkan harga file.\n\n"
        "Minimal: 1000"
    )

    await state.set_state(UploadState.wait_price)

@router.callback_query(F.data == "file_free")
async def file_free(call: CallbackQuery, state: FSMContext):

    await call.answer()

    await state.update_data(
        is_paid=False,
        price=0,
        payment_provider=None
    )

    await call.message.edit_text("⏳ Menyimpan file...")

    await finalize_save(call.message, state)
    
# =========================
# FINAL SAVE
# =========================
async def finalize_save(message: Message, state: FSMContext):

    async with get_lock(message.from_user.id):

        data = await state.get_data()

        media = data.get("media", [])
        share_media = data.get("share_media", True)
        folder_name = data.get("folder_name", "Folder AUTO")
        expiry = data.get("expiry", 0)

        if not media:
            return await message.answer("❌ No media found")

        expires_at = None
        if expiry > 0:
            expires_at = int(time.time()) + expiry

        pool = await get_pool()

        while True:
            code = "EFB-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

            exists = await pool.fetchval(
                "SELECT 1 FROM files WHERE code=$1",
                code
            )

            if not exists:
                break

        share_link = f"{BOT_URL}?start=getFile_{code}"

        await pool.execute(
            """
            INSERT INTO files (code, media, share_media, owner_id, media_count, expires_at)
            VALUES ($1,$2,$3,$4,$5,$6)
            """,
            code,
            json.dumps(media),
            share_media,
            message.from_user.id,
            len(media),
            expires_at
        )

        await state.clear()

        status = "PUBLIC" if share_media else "PRIVATE"

        text = (
            "✅ <b>FILE SAVED SUCCESSFULLY</b>\n\n"
            f"📝 Folder Name: {folder_name}\n"
            f"📋 Files: {len(media)}\n"
            f"🔑 Code: <code>{code}</code>\n"
            f"📤 Share Mode: {status}\n"
            f"🕒 Auto Delete: {expiry}s\n"
            f"🔗 Link: {share_link}"
        )

        await message.answer(text, parse_mode="HTML")

        try:
            await message.bot.send_message(
                CHANNEL_ID,
                text + f"\n\n👤 USER: <code>{message.from_user.id}</code>",
                parse_mode="HTML"
            )
        except:
            pass
