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

from config import CHANNEL_ID
from database import get_pool

from utils.force_sub import check_force_sub
from keyboards.join import join_kb


# =========================
# GLOBAL CONFIG
# =========================
MAX_MEDIA = 200
UPDATE_DELAY = 0.5 # anti spam edit (detik)

router = Router()

_last_update: dict[int, float] = {}  # user_id: last_update_time
_user_locks: dict[int, asyncio.Lock] = {}

# =========================
# SAFE EDIT MESSAGE
# =========================
async def safe_update(bot, chat_id, message_id, text, user_id):
    now = time.time()

    last = _last_update.get(user_id, 0)

    # ⛔ throttle
    if now - last < UPDATE_DELAY:
        return

    _last_update[user_id] = now

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text
        )

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return

    except Exception:
        # silent fail (biar tidak spam log)
        pass
# =========================
# STATE
# =========================
class UploadState(StatesGroup):
    wait_type = State()
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
@router.callback_query(F.data == "upfile")
async def start_upfile(call: CallbackQuery, state: FSMContext):

    # =========================
    # CLEAR STATE LAMA
    # =========================
    await state.clear()

    # =========================
    # FORCE SUB CHECK
    # =========================
    if not await check_force_sub(call.bot, call.from_user.id):
        return await call.message.answer(
            "❌ Join channel terlebih dahulu",
            reply_markup=join_kb()
        )

    # =========================
    # SEND UPLOAD UI
    # =========================
    msg = await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📤 KIRIM MEDIA SEKARANG"
    )

    # =========================
    # INIT STATE (FIXED & CONSISTENT)
    # =========================
    await state.update_data(
        media=[],
        idle_msg_id=msg.message_id,
        progress_msg_id=None,
        upload_mode=True,
        total_received=0,
        saved=False,
        type=None,
        is_paid=False,
        price=0
    )

    await call.answer()
# =========================
# RECEIVE MEDIA
# =========================
@router.message(F.document | F.video | F.photo)
async def receive_media(message: Message, state: FSMContext):

    user_id = message.from_user.id

    # =========================
    # USER LOCK (SAFE INIT)
    # =========================
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()

    async with _user_locks[user_id]:

        data = await state.get_data()

        # =========================
        # VALIDASI MODE UPLOAD
        # =========================
        if not data.get("upload_mode"):
            return

        media = data.get("media", [])
        total = data.get("total_received", 0)

        # =========================
        # LIMIT SAFETY
        # =========================
        if len(media) >= 200:
            return await message.answer("❌ Maksimal 200 media")

        # =========================
        # DETECT FILE
        # =========================
        if message.document:
            fid = message.document.file_id
            ftype = "document"
        elif message.video:
            fid = message.video.file_id
            ftype = "video"
        else:
            fid = message.photo[-1].file_id
            ftype = "photo"

        # =========================
        # APPEND MEDIA
        # =========================
        media.append({"file_id": fid, "type": ftype})
        total += 1

        await state.update_data(media=media, total_received=total)

        # delete user message (clean UI)
        try:
            await message.delete()
        except:
            pass

        # =========================
        # INIT PROGRESS (FIRST MEDIA ONLY)
        # =========================
        if total == 1:

            idle_id = data.get("idle_msg_id")

            if idle_id:
                try:
                    await message.bot.delete_message(message.chat.id, idle_id)
                except:
                    pass

            progress = await message.bot.send_message(
                message.chat.id,
                "📦 UPLOADING...\n[░░░░░░░░░░]\n0/200"
            )

            await state.update_data(progress_msg_id=progress.message_id)

            msg_id = progress.message_id

        else:
            msg_id = data.get("progress_msg_id")

        # =========================
        # SAFETY CHECK (IMPORTANT)
        # =========================
        if not msg_id:
            return

        # =========================
        # PROGRESS BAR
        # =========================
        bar_len = 10
        filled = int((total / 200) * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        text = (
            "📦 UPLOADING...\n"
            f"[{bar}]\n"
            f"{total}/200\n"
            "✅ accepted"
        )

        await safe_update(message.bot, message.chat.id, msg_id, text, user_id)

        # =========================
        # BUTTON (ANTI SPAM EDIT FIX)
        # =========================
        if total == 1 or total % 5 == 0:
            # update button tidak tiap message (biar tidak spam API)

            kb = InlineKeyboardBuilder()
            kb.button(text="⏹ STOP & SAVE", callback_data="save_upfile")
            kb.button(text="❌ CANCEL", callback_data="cancel_upfile")
            kb.adjust(2)

            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=msg_id,
                    reply_markup=kb.as_markup()
                )
            except:
                pass
# =========================
# CANCEL
# =========================
@router.callback_query(F.data == "cancel_upfile")
async def cancel(call: CallbackQuery, state: FSMContext):

    await state.clear()
    await call.answer("Upload dibatalkan", show_alert=True)

    await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n❌ CANCELLED"
    )


# =========================
# SAVE → TYPE
# =========================
@router.callback_query(F.data == "save_upfile")
async def choose_type(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()

    # =========================
    # VALIDASI MEDIA
    # =========================
    media = data.get("media")
    if not media:
        return await call.answer("❌ Media kosong", show_alert=True)

    # =========================
    # ANTI DOUBLE STATE FLOW
    # =========================
    if data.get("saved"):
        return await call.answer("⚠️ Sudah diproses", show_alert=True)

    # =========================
    # SET STATE
    # =========================
    await state.set_state(UploadState.wait_type)

    # =========================
    # BUILD KEYBOARD
    # =========================
    kb = InlineKeyboardBuilder()
    kb.button(text="🆓 FREE", callback_data="type_free")
    kb.button(text="💰 PAID", callback_data="type_paid")
    kb.adjust(2)

    # =========================
    # UPDATE UI
    # =========================
    try:
        await call.message.edit_text(
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n📦 PILIH TYPE",
            reply_markup=kb.as_markup()
        )
    except:
        pass

    await call.answer()
# =========================
# HANDLE TYPE
# =========================
@router.callback_query(F.data.startswith("type_"), UploadState.wait_type)
async def handle_type(call: CallbackQuery, state: FSMContext):

    choice = call.data.split("_")[1]

    # =========================
    # FREE
    # =========================
    if choice == "free":

        await state.update_data(
            file_type="free",
            is_paid=False,
            price=0
        )

        await call.answer("Free selected")

        # langsung final save
        return await finalize_save(call.message, state)

    # =========================
    # PAID
    # =========================
    if choice == "paid":

        await state.update_data(
            file_type="paid",
            is_paid=True,
            price=0  # sementara, nanti diisi user
        )

        await state.set_state(UploadState.wait_price)

        await call.answer()

        return await call.message.edit_text(
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n💰 MASUKKAN HARGA\n\nContoh: 5000"
        )
# =========================
# INPUT PRICE
# =========================
import re

@router.message(UploadState.wait_price)
async def input_price(message: Message, state: FSMContext):

    text = message.text.lower()

    # =========================
    # CLEAN INPUT (hapus rp, spasi, titik)
    # =========================
    cleaned = re.sub(r"[^0-9]", "", text)

    if not cleaned:
        return await message.answer("❌ Harga tidak valid")

    price = int(cleaned)

    # =========================
    # VALIDASI
    # =========================
    if price < 1000:
        return await message.answer("❌ Minimal harga 1000")

    if price > 100_000:
        return await message.answer("❌ Maksimal 100000")

    # =========================
    # SAVE
    # =========================
    await state.update_data(price=price)

    # =========================
    # CLEAN CHAT
    # =========================
    try:
        await message.delete()
    except:
        pass

    # =========================
    # CONTINUE FLOW
    # =========================
    await finalize_save(message, state)
# =========================
# DONE
# =========================
@router.callback_query(F.data == "done_upfile")
async def done(call: CallbackQuery, state: FSMContext):

    user_id = call.from_user.id

    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()

    async with _user_locks[user_id]:

        data = await state.get_data()
        media = data.get("media")

        if not media:
            return await call.answer("❌ No media", show_alert=True)

        if data.get("saved"):
            return await call.answer("⚠️ Sudah tersimpan", show_alert=True)

        await call.answer("⏳ Menyimpan...")

        saved = False

        try:
            await show_progress(call.message, len(media))
            await finalize_save(call.message, state)
            saved = True

        except Exception as e:
            print("SAVE ERROR:", e)
            try:
                await call.message.answer("❌ Gagal menyimpan data")
            except:
                pass

        finally:
            await state.update_data(saved=saved)
# =========================
# SAVE CORE (HARDENED)
# =========================
async def finalize_save(message: Message, state: FSMContext):

    pool = await get_pool()
    data = await state.get_data()

    # =========================
    # VALIDASI MEDIA
    # =========================
    media = data.get("media") or []
    if not media:
        return await message.answer("❌ Media kosong")

    # =========================
    # SAFE FIELD HANDLING
    # =========================
    is_paid = data.get("is_paid", False)

    file_type = data.get("file_type")
    if not file_type:
        file_type = "paid" if is_paid else "free"

    price = int(data.get("price") or 0)

    media_count = len(media)
    user = message.from_user

    # =========================
    # DETECT MEDIA TYPE (SAFE)
    # =========================
    first_item = media[0] if isinstance(media[0], dict) else {}

    first_type = first_item.get("type", "document")

    suffix_map = {
        "video": "v",
        "photo": "p",
        "document": "d"
    }

    suffix = suffix_map.get(first_type, "m")

    # =========================
    # GENERATE CODE
    # =========================
    code = await generate_unique_code(
        pool,
        media_count,
        suffix
    )

    # =========================
    # DATABASE TRANSACTION (SAFE)
    # =========================
    async with pool.acquire() as conn:
        async with conn.transaction():

            await conn.execute(
                """
                INSERT INTO files (
                    code, media, owner_id,
                    media_count, price, type, creator
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                """,
                code,
                json.dumps(media),
                user.id,
                media_count,
                price,
                file_type,
                user.full_name
            )

    # =========================
    # CLEAR STATE
    # =========================
    await state.clear()

    # =========================
    # FORMAT PRICE (CLEAN)
    # =========================
    price_text = "FREE" if price == 0 else f"Rp {price:,}".replace(",", ".")

    # =========================
    # OUTPUT MESSAGE
    # =========================
    text = (
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "✅ <b>UPLOAD SUCCESS</b>\n"
        "──────────────────\n\n"
        f"🔑 <b>CODE</b> : <code>{code}</code>\n"
        f"📦 <b>FILES</b> : {media_count}\n"
        f"💰 <b>TYPE</b> : {file_type.upper()}\n"
        f"💵 <b>PRICE</b> : {price_text}\n"
        f"👤 <b>OWNER</b> : {user.full_name}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    # =========================
    # SEND RESULT (SAFE)
    # =========================
    try:
        await message.edit_text(text, parse_mode="HTML")
    except:
        try:
            await message.answer(text, parse_mode="HTML")
        except:
            pass

    # =========================
    # LOG CHANNEL (SAFE)
    # =========================
    try:
        await message.bot.send_message(
            CHANNEL_ID,
            text,
            parse_mode="HTML"
        )
    except Exception as e:
        print("LOG CHANNEL ERROR:", e)
# =========================
# PROGRESS (OPTIMIZED)
# =========================

import asyncio
from aiogram.exceptions import TelegramBadRequest

async def show_progress(message, total):

    frames = [
        "⏳ MENYIMPAN",
        "⏳ MENYIMPAN.",
        "⏳ MENYIMPAN..",
        "⏳ MENYIMPAN..."
    ]

    last_text = None

    try:
        # =========================
        # LOADING ANIMATION
        # =========================
        for frame in frames:

            text = (
                "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n"
                f"{frame}\n"
                f"📦 {total} FILE"
            )

            # =========================
            # AVOID DUPLICATE EDIT
            # =========================
            if text == last_text:
                continue

            last_text = text

            try:
                await message.edit_text(text)
            except TelegramBadRequest as e:
                if "message is not modified" in str(e):
                    pass
                else:
                    break

            await asyncio.sleep(0.5)

        # =========================
        # SUCCESS STATE
        # =========================
        success_text = (
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "✅ SUCCESS SAVED\n"
            "──────────────────\n"
            f"📦 FILES: {total}\n"
            "━━━━━━━━━━━━━━━━━━"
        )

        try:
            await message.edit_text(success_text)
        except:
            try:
                await message.answer("✅ SUCCESS SAVED")
            except:
                pass

    except Exception as e:
        # fallback safety
        try:
            await message.answer("✅ SUCCESS SAVED")
        except:
            pass
        print("PROGRESS ERROR:", e)
