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

    await call.answer()
# =========================
# GENERATE CODE
# =========================
def generate_code():
    return "EF_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=16))


# =========================
# BUFFER MEDIA GROUP
# =========================
media_buffer = {}


# =========================
# RECEIVE MEDIA
# =========================
@router.message(F.document | F.video | F.photo)
async def receive_media(message: Message, state: FSMContext):

    data = await state.get_data()
    if not data.get("upload_mode"):
        return

    if message.document:
        fid = message.document.file_id
        ftype = "document"
    elif message.video:
        fid = message.video.file_id
        ftype = "video"
    else:
        fid = message.photo[-1].file_id
        ftype = "photo"

    item = {"file_id": fid, "type": ftype}

    media = data.get("media", [])
    media.append(item)
    await state.update_data(media=media)

    try:
        await message.delete()
    except:
        pass

    total = len(media)

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
        # langsung save kalau FREE
        await save_file(call.message, state)
        await state.update_data(upload_mode=False)

    await call.answer()

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
# DONE
# =========================
@router.callback_query(F.data == "done_upfile")
async def done(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()
    media = data.get("media", [])

    if not media:
        return await call.answer("❌ No media", show_alert=True)

    await show_progress(call.message, len(media))

    # prevent double execution
    if not data.get("upload_mode"):
        return await call.answer("⚠️ Already processed", show_alert=False)

    await state.update_data(upload_mode=False)

    await save_file(call.message, state)

    await call.answer()
# =========================
# SAVE CORE
# =========================
async def save_file(message: Message, state: FSMContext):

    pool = await get_pool()
    bot = message.bot

    data = await state.get_data()

    media = data.get("media", [])
    if not media:
        return

    media_json = json.dumps(media)

    file_type = data.get("type", "free")
    price = data.get("price", 0)

    code = generate_code()
    user = message.from_user

    await pool.execute(
        """
        INSERT INTO files (code, media, owner_id, media_count, price, type, creator)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        """,
        code,
        media_json,
        user.id,
        len(media),
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
        f"🔑 𝗖𝗢𝗗𝗘   : <code>{code}</code>\n"
        f"📊 𝗠𝗘𝗗𝗜𝗔  : {len(media)} FILE\n"
        f"💰 𝗧𝗬𝗣𝗘   : {file_type.upper()}\n"
        f"👤 𝗢𝗪𝗡𝗘𝗥  : {user.full_name}\n\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    try:
        await message.edit_text(text, parse_mode="HTML")
    except:
        await message.answer(text, parse_mode="HTML")

    try:
        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
    except:
        pass
# =========================
# PROGRESS
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

        await asyncio.sleep(0.15)
