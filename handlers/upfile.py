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
# GLOBAL CONFIG
# =========================
MAX_MEDIA = 200
UPDATE_DELAY = 0.25

_last_update: dict[int, float] = {}

_lock_init = asyncio.Lock()
_user_locks: dict[int, asyncio.Lock] = {}

def get_lock(user_id: int) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock
# =========================
# SAFE EDIT MESSAGE
# =========================
async def safe_update(bot, chat_id, message_id, text, user_id):
    now = time.time()
    last = _last_update.get(user_id, 0)

    wait = UPDATE_DELAY - (now - last)
    if wait > 0:
        await asyncio.sleep(wait)

    try:
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id
        )

        # 🔥 update timestamp ONLY kalau sukses
        _last_update[user_id] = time.time()

    except TelegramBadRequest:
        return

    except Exception:
        return
# =========================
# STATE
# =========================
class UploadState(StatesGroup):
    upload = State()
    wait_price = State()

# =========================
# GENERATE CODE (PREMIUM LONG STYLE)
# =========================
def generate_code(media_count: int, media_type: str) -> str:

    type_map = {
        "photo": "p",
        "video": "v",
        "document": "d",
        "mixed": "m"
    }

    type_part = type_map.get(media_type, "m")

    rand_part = ''.join(
        random.choices(string.ascii_letters + string.digits, k=18)
    )

    return f"EFB-{type_part}-{media_count}-{rand_part}"
# =========================
# GENERATE UNIQUE CODE (NEW)
# =========================
async def generate_unique_code(pool, media_count, media_type):

    for _ in range(5):
        code = generate_code(media_count, media_type)

        exists = await pool.fetchval(
            "SELECT 1 FROM files WHERE code=$1",
            code
        )

        if not exists:
            return code

    # fallback super safe (tetap format sama)
    rand = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    return f"EFB-m-{media_count}-{rand}"
# =========================
# START UPFILE
# =========================
import time

@router.callback_query(F.data == "upfile")
async def start_upfile(call: CallbackQuery, state: FSMContext):

    await call.answer()

    async with get_lock(call.from_user.id):

        await state.clear()

        ok = await check_force_sub(call.bot, call.from_user.id)
        if not ok:
            return await call.message.answer(
                "❌ Join channel terlebih dahulu",
                reply_markup=join_kb()
            )

        text_final = "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n📤 SEND MEDIA NOW"

        try:
            # =========================
            # STEP 1: ALWAYS SHOW LOADING FIRST
            # =========================
            msg = await call.message.edit_text("⏳ Loading...")

            # optional kecil delay biar smooth feel (bukan delay nyata user)
            await asyncio.sleep(0.15)

            # =========================
            # STEP 2: FINAL UI
            # =========================
            msg = await msg.edit_text(text_final)

        except TelegramBadRequest:
            msg = call.message

        await state.update_data(
            upload_mode=True,
            media=[],
            progress_msg_id=msg.message_id,
            total_received=0,
            file_type=None,
            is_paid=False,
            price=0,
            saving=False,
            finalizing=False
        )
# =========================
# RECEIVE MEDIA
# =========================
@router.message(F.document | F.video | F.photo)
async def receive_media(message: Message, state: FSMContext):

    user_id = message.from_user.id
    lock = get_lock(user_id)

    async with lock:

        data = await state.get_data()

        if not data or data.get("upload_mode") is not True:
            return

        media = data.get("media") or []

        if len(media) >= MAX_MEDIA:
            return await message.answer("❌ Maksimal 200 media")

        # detect file
        if message.document:
            fid = message.document.file_id
            ftype = "document"
        elif message.video:
            fid = message.video.file_id
            ftype = "video"
        elif message.photo:
            fid = message.photo[-1].file_id
            ftype = "photo"
        else:
            return

        media.append({"file_id": fid, "type": ftype})
        await state.update_data(media=media)

        try:
            await message.delete()
        except:
            pass

        msg_id = data.get("progress_msg_id")

        # =========================
        # CREATE PROGRESS ONCE
        # =========================
        if not msg_id:
            kb = InlineKeyboardBuilder()
            kb.button(text="⏹ STOP & SAVE", callback_data="save_upfile")
            kb.button(text="❌ CANCEL", callback_data="cancel_upfile")
            kb.adjust(2)

            progress = await message.bot.send_message(
                chat_id=message.chat.id,
                text="📦 UPLOADING...\n[░░░░░░░░░░]\n0/200",
                reply_markup=kb.as_markup(),
                reply_to_message_id=message.message_id
            )

            msg_id = progress.message_id
            await state.update_data(progress_msg_id=msg_id)

        # =========================
        # UPDATE ONLY TEXT
        # =========================
        total = len(media)

        bar_len = 10
        filled = min(bar_len, int(total / MAX_MEDIA * bar_len))
        bar = "█" * filled + "░" * (bar_len - filled)

        text = (
            "📦 UPLOADING...\n"
            f"[{bar}]\n"
            f"{total}/{MAX_MEDIA}\n"
            "✅ accepted"
        )

        await safe_update(
            message.bot,
            message.chat.id,
            msg_id,
            text,
            user_id
        )
# =========================
# CANCEL
# =========================
@router.callback_query(F.data == "cancel_upfile")
async def cancel(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()

    await state.update_data(upload_stopped=True)

    await state.clear()

    await call.answer("Upload dibatalkan", show_alert=True)

    try:
        await call.message.edit_text(
            "❌ UPLOAD CANCELLED"
        )
    except:
        pass
# =========================
# SAVE → TYPE
# =========================
@router.callback_query(F.data == "save_upfile")
async def choose_type(call: CallbackQuery, state: FSMContext):

    user_id = call.from_user.id
    lock = await get_final_lock(user_id)

    async with lock:

        data = await state.get_data()

        # =========================
        # HARD GUARD
        # =========================
        if not data.get("media"):
            return await call.answer("❌ No media", show_alert=True)

        if data.get("finalizing"):
            return await call.answer("⏳ Already processing...", show_alert=True)

        # 🔥 set lock state immediately (anti double click)
        await state.update_data(finalizing=True)

        kb = InlineKeyboardBuilder()
        kb.button(text="🆓 FREE", callback_data="type_free")
        kb.button(text="💰 PAID", callback_data="type_paid")
        kb.adjust(2)

        await state.set_state(UploadState.upload)

        try:
            await call.message.edit_text(
                "📦 PILIH TYPE",
                reply_markup=kb.as_markup()
            )
        except TelegramBadRequest:
            pass
    )
# =========================
# HANDLE TYPE
# =========================
@router.callback_query(F.data.startswith("type_"))
async def handle_type(call: CallbackQuery, state: FSMContext):

    user_id = call.from_user.id
    lock = await get_final_lock(user_id)

    async with lock:

        data = await state.get_data()

        if data.get("finalizing"):
            return await call.answer("⏳ Processing...", show_alert=True)

        choice = call.data.split("_")[1]

        # =========================
        # FREE FLOW (NO INPUT PRICE)
        # =========================
        if choice == "free":

            await state.update_data(
                file_type="free",
                is_paid=False,
                price=0,
                finalizing=True
            )

            await call.answer()

            # ⚠️ IMPORTANT: STOP UI FLOW TOTAL
            await call.message.edit_text("⏳ Saving...")

            await finalize_save(call.message, state)
            return

        # =========================
        # PAID FLOW (GO TO PRICE)
        # =========================
        await state.update_data(
            file_type="paid",
            is_paid=True
        )

        await state.set_state(UploadState.wait_price)

        await call.answer()
        await call.message.edit_text("💰 INPUT PRICE")
# =========================
# INPUT PRICE
# =========================
@router.message(UploadState.wait_price)
async def input_price(message: Message, state: FSMContext):

    if not message.text:
        return await message.answer("❌ Invalid")

    cleaned = re.sub(r"[^0-9]", "", message.text)

    if not cleaned:
        return await message.answer("❌ Invalid")

    price = int(cleaned)

    if price < 1000 or price > 100000:
        return await message.answer("❌ Range 1000 - 100000")

    await state.update_data(
        price=price,
        finalizing=False  # reset dulu
    )

    try:
        await message.delete()
    except:
        pass

    await finalize_save(message, state)
# =========================
# DONE
# =========================
async def finalize_save(message: Message, state: FSMContext):

    user_id = message.from_user.id

    async with get_lock(user_id):

        data = await state.get_data()

        # 🔒 HARD GUARD (anti double trigger)
        if data.get("saving") is True:
            return

        await state.update_data(saving=True)

        try:
            media = data.get("media") or []

            if not media:
                return await message.answer("❌ No media")

            file_type = data.get("file_type") or "free"
            is_paid = data.get("is_paid", file_type == "paid")
            price = int(data.get("price") or 0) if is_paid else 0

            pool = await get_pool()

            code = await generate_unique_code(pool, len(media), file_type)

            # =========================
            # DB INSERT
            # =========================
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO files
                    (code, media, owner_id, media_count, price, type, creator)
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    """,
                    code,
                    json.dumps(media),
                    user_id,
                    len(media),
                    price,
                    file_type,
                    message.from_user.full_name
                )

            # =========================
            # CLEAN OUTPUT (EASY COPY UX)
            # =========================
            text = (
                "💎 PREMIUM SAVED\n" if is_paid else "🎉 FREE SAVED\n"
            ) + (
                f"\n🔑 CODE:\n`{code}`\n"
                f"📦 MEDIA: {len(media)}\n"
                f"💰 PRICE: Rp {price:,}"
                if is_paid else
                f"\n🔑 CODE:\n`{code}`\n📦 MEDIA: {len(media)}"
            )

            # =========================
            # CLEAR STATE SAFELY
            # =========================
            await state.clear()

            # send result
            await message.answer(text, parse_mode="Markdown")

            # optional channel log
            await message.bot.send_message(CHANNEL_ID, text)

        finally:
            # jangan crash kalau state sudah clear
            try:
                await state.update_data(saving=False)
            except:
                pass
