import asyncio
import json
import random
import string

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


MAX_MEDIA = 50

router = Router()
# =========================
# STATE
# =========================
class UploadState(StatesGroup):
    wait_type = State()
    wait_price = State()
# =========================
# GENERATE CODE
# =========================
def generate_code(media_count: int, media_type: str):

    random_part = "".join(
        random.choices(
            string.ascii_letters + string.digits,
            k=20
        )
    )

    return f"EFB_{random_part}_{media_count}{media_type}"

# =========================
# START UPFILE
# =========================
@router.callback_query(F.data == "upfile")
async def start_upfile(call: CallbackQuery, state: FSMContext):

    await state.clear()

    if not await check_force_sub(
        call.bot,
        call.from_user.id
    ):
        return await call.message.answer(
            "❌ Join channel terlebih dahulu",
            reply_markup=join_kb()
        )

    msg = await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n📤 KIRIM MEDIA (foto / video / dokumen)"
    )

    await state.update_data(
        media=[],
        upload_mode=True,
        preview_msg_id=msg.message_id,
        saved=False
    )

    await call.answer()
# =========================
# RECEIVE MEDIA
# =========================
@router.message(F.document | F.video | F.photo)
async def receive_media(message: Message, state: FSMContext):

    data = await state.get_data()

    if not data.get("upload_mode"):
        return

    media = data.get("media", [])

    if len(media) >= MAX_MEDIA:
        return await message.answer(
            "❌ Maksimal 50 media per produk"
        )

    if message.document:
        fid = message.document.file_id
        ftype = "document"
    elif message.video:
        fid = message.video.file_id
        ftype = "video"
    else:
        fid = message.photo[-1].file_id
        ftype = "photo"

    media.append({
        "file_id": fid,
        "type": ftype
    })

    await state.update_data(media=media)

    try:
        await message.delete()
    except:
        pass

    total = len(media)

    text = (
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📦 𝗣𝗥𝗢𝗖𝗘𝗦𝗦𝗜𝗡𝗚\n"
        "──────────────────\n"
        f"📊 COUNT : {total}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="💾 SAVE", callback_data="save_upfile")
    kb.button(text="❌ CANCEL", callback_data="cancel_upfile")
    kb.adjust(2)

    preview_id = data.get("preview_msg_id")

    if preview_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=preview_id,
                text=text,
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
# TYPE HANDLER
# =========================
@router.callback_query(F.data.startswith("type_"))
async def set_type(call: CallbackQuery, state: FSMContext):

    t = call.data.split("_")[1]
    await state.update_data(type=t)

    if t == "paid":
        await state.set_state(UploadState.wait_price)

        await call.message.edit_text(
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n💰 MASUKKAN HARGA"
        )
    else:
        await finalize_save(call.message, state)

    await call.answer()


# =========================
# PRICE INPUT
# =========================
@router.message(UploadState.wait_price)
async def input_price(message: Message, state: FSMContext):

    raw = "".join(filter(str.isdigit, message.text or ""))

    if not raw:
        return await message.answer(
            "❌ Format harga salah"
        )

    price = int(raw)

    if price < 100:
        return await message.answer(
            "❌ Minimal harga Rp100"
        )

    await state.update_data(price=price)

    kb = InlineKeyboardBuilder()
    kb.button(
        text="✅ DONE",
        callback_data="done_upfile"
    )
    kb.button(
        text="❌ CANCEL",
        callback_data="cancel_upfile"
    )
    kb.adjust(2)

    await message.answer(
        f"𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n"
        f"💰 HARGA : Rp{price:,}\n\n"
        f"Klik DONE untuk menyimpan",
        reply_markup=kb.as_markup()
    )


# =========================
# DONE
# =========================@router.callback_query(F.data == "done_upfile")
async def done(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()

    if not data.get("media"):
        return await call.answer("❌ No media", show_alert=True)

    if data.get("saved"):
        return await call.answer("⚠️ Sudah tersimpan", show_alert=True)

    # LOCK dulu biar anti double click
    await state.update_data(saved=True)

    await call.answer("⏳ Menyimpan file...")

    await show_progress(call.message, len(data["media"]))

    await finalize_save(call.message, state)


# =========================
# SAVE CORE (FIXED)
# =========================
async def finalize_save(message: Message, state: FSMContext):

    pool = await get_pool()
    data = await state.get_data()

    media = data.get("media", [])
    if not media:
        return

    file_type = data.get("type", "free")
    price = data.get("price", 0)

    media_count = len(media)

    first_type = media[0]["type"]

    if first_type == "video":
        suffix = "v"
    elif first_type == "photo":
        suffix = "p"
    else:
        suffix = "d"

    code = generate_code(media_count, suffix)

    user = message.from_user

    await pool.execute(
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

    await state.clear()

    text = (
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📦 𝗦𝗨𝗖𝗖𝗘𝗦𝗦 𝗦𝗔𝗩𝗘𝗗\n"
        "──────────────────\n\n"
        f"🔑 CODE : <code>{code}</code>\n"
        f"📊 MEDIA : {media_count} FILE\n"
        f"💰 TYPE : {file_type.upper()}\n"
        f"👤 OWNER : {user.full_name}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    try:
        await message.edit_text(text, parse_mode="HTML")
    except:
        await message.answer(text, parse_mode="HTML")

    try:
        await message.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
    except:
        pass


# =========================
# PROGRESS
# =========================
async def show_progress(message, total):

    last = 0

    for i in range(1, total + 1):

        # biar gak spam edit tiap langkah kecil (lebih smooth)
        if i - last < 1:
            continue

        last = i

        try:
            await message.edit_text(
                f"𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n"
                f"⏳ UPLOADING\n"
                f"📊 {i}/{total}"
            )

        except TelegramBadRequest:
            # kalau message sudah tidak bisa diedit, skip
            pass

        except Exception:
            pass

        await asyncio.sleep(0.2)
