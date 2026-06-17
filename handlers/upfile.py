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
UPDATE_DELAY = 0.3  # anti spam edit (detik)

router = Router()

_last_update = {}  # user_id: last_update_time
_user_locks = {}

# =========================
# SAFE EDIT MESSAGE
# =========================
async def safe_update(bot, chat_id, message_id, text, user_id):
    now = time.time()

    last = _last_update.get(user_id, 0)

    # ⛔ throttle biar gak spam edit
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
        # ❗ ignore kalau text sama
        if "message is not modified" in str(e):
            return
        print("TelegramBadRequest:", e)

    except Exception as e:
        print("safe_update error:", e)
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
        "document": "d"
    }

    type_part = type_map.get(media_type, "m")

    # random panjang (premium feel)
    rand_part = ''.join(random.choices(
        string.ascii_letters + string.digits,
        k=18
    ))

    return f"EFB-{media_count}{type_part}-{rand_part}"
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

    # fallback super rare
    return f"EFB-{media_count}{int(time.time())}"
# =========================
# START UPFILE
# =========================
@router.callback_query(F.data == "upfile")
async def start_upfile(call: CallbackQuery, state: FSMContext):

    await state.clear()

    if not await check_force_sub(call.bot, call.from_user.id):
        return await call.message.answer(
            "❌ Join channel terlebih dahulu",
            reply_markup=join_kb()
        )

    msg = await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n━━━━━━━━━━━━━━━━━━\n\n📤 KIRIM MEDIA SEKARANG"
    )

    await state.update_data(
        media=[],
        idle_msg_id=msg.message_id,
        progress_msg_id=None,
        upload_mode=True,
        total_received=0,
        locked=False
    )

    await call.answer()
# =========================
# RECEIVE MEDIA
# =========================
@router.message(F.document | F.video | F.photo)
async def receive_media(message: Message, state: FSMContext):

    user_id = message.from_user.id

    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()

    async with _user_locks[user_id]:

        data = await state.get_data()
        if not data.get("upload_mode"):
            return

        media = data.get("media", [])
        total = data.get("total_received", 0)

        if len(media) >= 200:
            return await message.answer("❌ Maksimal 200 media")

        # detect file
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
        total += 1

        await state.update_data(media=media, total_received=total)

        try:
            await message.delete()
        except:
            pass

        # =========================
        # 🔥 FIRST MEDIA → HAPUS WELCOME + BUAT PROGRESS
        # =========================
        if total == 1:

            idle_id = data["idle_msg_id"]

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
            msg_id = data["progress_msg_id"]

        # =========================
        # PROGRESS UPDATE
        # =========================
        bar_len = 10
        filled = int(total / 200 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        text = (
            "📦 UPLOADING...\n"
            f"[{bar}]\n"
            f"{total}/200\n"
            f"✅ accepted"
        )

        await safe_update(message.bot, message.chat.id, msg_id, text, user_id)

        # =========================
        # 🔥 BUTTON MUNCUL SAAT SUDAH ADA PROGRESS
        # =========================
        if total >= 1:

            kb = InlineKeyboardBuilder()
            kb.button(text="⏹ STOP & SAVE", callback_data="save_upfile")
            kb.button(text="❌ CANCEL", callback_data="cancel_upfile")
            kb.adjust(2)

            await message.bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=msg_id,
                reply_markup=kb.as_markup()
            )
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

    if not data.get("media"):
        return await call.answer("❌ Media kosong", show_alert=True)

    await state.set_state(UploadState.wait_type)

    kb = InlineKeyboardBuilder()
    kb.button(text="🆓 FREE", callback_data="type_free")
    kb.button(text="💰 PAID", callback_data="type_paid")
    kb.adjust(2)

    await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n📦 PILIH TYPE",
        reply_markup=kb.as_markup()
    )

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
            is_paid=False,
            price=0
        )

        return await finalize_upload(call, state)

    # =========================
    # PAID
    # =========================
    if choice == "paid":

        await state.update_data(is_paid=True)

        await state.set_state(UploadState.wait_price)

        return await call.message.edit_text(
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n💰 MASUKKAN HARGA\n\nContoh: 5000"
        )
# =========================
# INPUT PRICE
# =========================
@router.message(UploadState.wait_price)
async def input_price(message: Message, state: FSMContext):

    if not message.text.isdigit():
        return await message.answer("❌ Harga harus angka")

    price = int(message.text)

    # optional limit
    if price < 1000:
        return await message.answer("❌ Minimal harga 1000")

    if price > 100_000:
        return await message.answer("❌ Maksimal 100000")

    await state.update_data(price=price)

    # hapus pesan user biar clean
    try:
        await message.delete()
    except:
        pass

    await finalize_upload(message, state)
# =========================
# DONE
# =========================
@router.callback_query(F.data == "done_upfile")
async def done(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()

    # =========================
    # VALIDASI
    # =========================
    if not data.get("media"):
        return await call.answer("❌ No media", show_alert=True)

    if data.get("saved"):
        return await call.answer("⚠️ Sudah tersimpan", show_alert=True)

    # =========================
    # LOCK CEPAT (ANTI SPAM KLIK)
    # =========================
    await state.update_data(saved=True)

    await call.answer("⏳ Menyimpan...")

    try:
        # =========================
        # PROGRESS UI
        # =========================
        await show_progress(call.message, len(data["media"]))

        # =========================
        # FINAL SAVE
        # =========================
        await finalize_save(call.message, state)

    except Exception as e:
        # =========================
        # UNLOCK KALAU GAGAL
        # =========================
        await state.update_data(saved=False)

        await call.message.answer("❌ Gagal menyimpan")
        print("SAVE ERROR:", e)
# =========================
# SAVE CORE (HARDENED)
# =========================
async def finalize_save(message: Message, state: FSMContext):

    pool = await get_pool()
    data = await state.get_data()

    media = data.get("media", [])
    if not media:
        return await message.answer("❌ Media kosong")

    # =========================
    # AMBIL DATA
    # =========================
    file_type = data.get("type", "free")
    price = int(data.get("price", 0))
    media_count = len(media)

    user = message.from_user

    # =========================
    # DETECT TYPE
    # =========================
    first_type = media[0]["type"]

    if first_type == "video":
        suffix = "v"
    elif first_type == "photo":
        suffix = "p"
    else:
        suffix = "d"

    # =========================
    # GENERATE UNIQUE CODE (WAJIB)
    # =========================
    code = await generate_unique_code(
        pool,
        media_count,
        suffix
    )

    # =========================
    # SAVE (TRANSACTION BIAR AMAN)
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
    # FORMAT OUTPUT (LEBIH PREMIUM)
    # =========================
    text = (
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "✅ <b>SUCCESS SAVED</b>\n"
        "──────────────────\n\n"
        f"🔑 <b>CODE</b> : <code>{code}</code>\n"
        f"📦 <b>FILES</b> : {media_count}\n"
        f"💰 <b>TYPE</b> : {file_type.upper()}\n"
        f"👤 <b>OWNER</b> : {user.full_name}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    # =========================
    # SEND RESULT
    # =========================
    try:
        await message.edit_text(text, parse_mode="HTML")
    except:
        await message.answer(text, parse_mode="HTML")

    # =========================
    # LOG KE CHANNEL (OPTIONAL)
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
async def show_progress(message, total):

    text = (
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n"
        "⏳ MENYIMPAN...\n"
        f"📦 {total} FILE"
    )

    try:
        await message.edit_text(text)
    except:
        pass

    # delay kecil biar kerasa proses
    await asyncio.sleep(0.8)

    try:
        await message.edit_text(
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n"
            "✅ SUCCESS\n"
            f"📦 {total} FILE TERSIMPAN"
        )
    except:
        pass
