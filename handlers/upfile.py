import random
import string
import json
import asyncio

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_pool
from config import CHANNEL_ID

router = Router()


# =========================
# STATE
# =========================
class UploadState(StatesGroup):
    wait_type = State()
    wait_price = State()


# =========================
# ENTRY UPFILE
# =========================
@router.callback_query(F.data == "upfile")
async def start_upfile(call: CallbackQuery, state: FSMContext):

    await state.clear()

    msg = await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n📤 KIRIM MEDIA (foto / video / dokumen)"
    )

    await state.update_data(
        media=[],
        upload_mode=True,
        preview_msg_id=msg.message_id
    )


# =========================
# GENERATE CODE
# =========================
def generate_code():
    return "EF_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=16))


# =========================
# RECEIVE MEDIA (ANTI NUMPUK + 1 MESSAGE UI)
# =========================
media_buffer = {}


@router.message(F.document | F.video | F.photo)
async def receive_media(message: Message, state: FSMContext):

    data = await state.get_data()

    if not data.get("upload_mode"):
        return

    # =========================
    # DETECT FILE
    # =========================
    if message.document:
        file_id = message.document.file_id
    elif message.video:
        file_id = message.video.file_id
    else:
        file_id = message.photo[-1].file_id

    item = {"file_id": file_id}

    # =========================
    # MEDIA GROUP MODE
    # =========================
    if message.media_group_id:
        gid = message.media_group_id

        if gid not in media_buffer:
            media_buffer[gid] = []

        media_buffer[gid].append(item)

        # tunggu semua masuk
        await asyncio.sleep(1)

        # kalau masih ada di buffer → proses
        if gid in media_buffer:
            batch = media_buffer.pop(gid)

            data = await state.get_data()
            media = data.get("media", [])

            media.extend(batch)

            await state.update_data(media=media)

    else:
        # =========================
        # SINGLE FILE
        # =========================
        media = data.get("media", [])
        media.append(item)
        await state.update_data(media=media)

    # =========================
    # DELETE USER MSG
    # =========================
    try:
        await message.delete()
    except:
        pass

    # =========================
    # UI UPDATE
    # =========================
    data = await state.get_data()
    total = len(data.get("media", []))

    text = f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

📦 𝗣𝗥𝗢𝗖𝗘𝗦𝗦𝗜𝗡𝗚
────────────────
📊 𝗖𝗢𝗨𝗡𝗧 : {total}
"""

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

    await call.message.edit_text("𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n❌ CANCELLED")


# =========================
# SAVE → TYPE SELECT
# =========================
@router.callback_query(F.data == "save_upfile")
async def choose_type(call: CallbackQuery, state: FSMContext):

    await state.set_state(UploadState.wait_type)

    kb = InlineKeyboardBuilder()
    kb.button(text="🆓 FREE", callback_data="type_free")
    kb.button(text="💰 PAID", callback_data="type_paid")
    kb.adjust(2)

    await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n📦 PILIH TYPE",
        reply_markup=kb.as_markup()
    )


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
        await save_file(call, state, price=0)


# =========================
# PRICE INPUT
# =========================
@router.message(UploadState.wait_price)
async def input_price(message: Message, state: FSMContext):

    raw = "".join(filter(str.isdigit, message.text or ""))

    if not raw:
        await message.answer("❌ Format salah")
        return

    price = int(raw)

    await state.update_data(price=price)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ DONE", callback_data="done_upfile")
    kb.button(text="❌ CANCEL", callback_data="cancel_upfile")
    kb.adjust(2)

    await message.answer(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n⚙️ KONFIRMASI",
        reply_markup=kb.as_markup()
    )


# =========================
# DONE + PROGRESS
# =========================
@router.callback_query(F.data == "done_upfile")
async def done(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()
    media = data.get("media", [])

    if not media:
        await call.answer("❌ No media", show_alert=True)
        return

    await show_progress(call.message, len(media))
    await save_file(call, state)


# =========================
# SAVE CORE
# =========================
async def save_file(event, state: FSMContext, price=None):

    pool = await get_pool()
    bot: Bot = event.bot

    data = await state.get_data()

    media = data.get("media", [])
    if not media:
        await event.answer("❌ Tidak ada media")
        return

    media_json = [{"file_id": m} for m in media]
    media_count = len(media)

    file_type = data.get("type", "free")
    price = price if price is not None else data.get("price", 0)

    code = generate_code()
    user = event.from_user

    await pool.execute(
        """
        INSERT INTO files (code, file_id, owner_id, media_count, price, type, creator)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        """,
        code,
        json.dumps(media_json),
        user.id,
        media_count,
        price,
        file_type,
        user.full_name
    )

    await state.clear()

    text = f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

📦 𝗠𝗘𝗗𝗜𝗔 𝗦𝗨𝗖𝗖𝗘𝗦𝗦 𝗦𝗔𝗩𝗘𝗗
────────────────
🔑 𝗖𝗢𝗗𝗘
<code>{code}</code>

📊 𝗠𝗘𝗗𝗜𝗔 : {media_count}
💰 𝗦𝗬𝗦𝗧𝗘𝗠 : {file_type.upper()} {price}
👤 𝗖𝗥𝗘𝗔𝗧𝗘 : {user.full_name}
"""

    try:
        await event.message.edit_text(text, parse_mode="HTML")
    except:
        pass

    try:
        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
    except:
        pass


# =========================
# PROGRESS ANIMATION
# =========================
async def show_progress(message, total):

    for i in range(1, total + 1):

        text = f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

⏳ 𝗨𝗣𝗟𝗢𝗔𝗗𝗜𝗡𝗚
────────────────
📊 {i}/{total}
"""

        try:
            await message.edit_text(text)
        except:
            pass

        await asyncio.sleep(0.2)
