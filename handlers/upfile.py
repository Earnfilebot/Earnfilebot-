import random
import string
import asyncio

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_pool
from config import CHANNEL_ID
from utils.ui_manager import update_ui
from utils.home import build_home
from keyboards.menu import home_kb

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
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧\n\n📤 KIRIM MEDIA (foto / video / dokumen)"
    )

    await state.update_data(
        media=[],
        preview_msg_id=msg.message_id
    )
# =========================
# GENERATE CODE
# =========================
def generate_code():
    return "EF_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=16))


# =========================
# RECEIVE MEDIA (LOCKED MODE)
# =========================
@router.message(F.document | F.video | F.photo)
async def receive_media(message: Message, state: FSMContext):

    data = await state.get_data()

    # ❌ ignore kalau bukan mode upload
    if not data.get("upload_mode"):
        return

    media = data.get("media", [])

    # ambil file_id
    if message.document:
        file_id = message.document.file_id
    elif message.video:
        file_id = message.video.file_id
    else:
        file_id = message.photo[-1].file_id

    media.append(file_id)
    await state.update_data(media=media)

    # 🔥 HAPUS MEDIA USER (BIAR CLEAN CHAT)
    try:
        await message.delete()
    except:
        pass

    total = len(media)

    text = f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

📦 𝗣𝗥𝗢𝗖𝗘𝗦𝗦𝗜𝗡𝗚 𝗠𝗘𝗗𝗜𝗔
📊 𝗖𝗢𝗨𝗡𝗧 : {total}
"""

    kb = InlineKeyboardBuilder()
    kb.button(text="💾 SAVE", callback_data="save_upfile")
    kb.button(text="❌ CANCEL", callback_data="cancel_upfile")
    kb.adjust(2)

    preview_id = data.get("preview_msg_id")

    # 🔥 UPDATE 1 MESSAGE (ANTI NUMPUK)
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
    else:
        msg = await message.answer(text, reply_markup=kb.as_markup())
        await state.update_data(preview_msg_id=msg.message_id)
# =========================
# CANCEL → BACK HOME CLEAN
# =========================
@router.callback_query(F.data == "cancel_upfile")
async def cancel(call: CallbackQuery, state: FSMContext):

    await state.clear()

    await call.answer("Upload dibatalkan", show_alert=True)

    user_id = call.from_user.id
    balance = 0

    await call.message.edit_text(
        build_home(user_id, balance),
        reply_markup=home_kb()
    )


# =========================
# SAVE → TYPE SELECT
# =========================
@router.callback_query(F.data == "save_upfile")
async def choose_type(call: CallbackQuery, state: FSMContext):

    kb = InlineKeyboardBuilder()
    kb.button(text="🆓 FREE", callback_data="type_free")
    kb.button(text="💰 PAID", callback_data="type_paid")
    kb.adjust(2)

    await state.set_state(UploadState.wait_type)

    await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧\n\n📦 PILIH TYPE",
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
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧\n\n💰 MASUKKAN HARGA\nContoh: 10000 / 10.000"
        )
    else:
        await save_file(call, state, price=0)


# =========================
# PRICE INPUT
# =========================
@router.message(UploadState.wait_price)
async def input_price(message: Message, state: FSMContext):

    raw = "".join(filter(str.isdigit, message.text))

    if not raw:
        await message.answer("❌ Format salah")
        return

    price = int(raw)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ DONE", callback_data="done_upfile")
    kb.button(text="❌ CANCEL", callback_data="cancel_upfile")
    kb.adjust(2)

    await state.update_data(price=price)

    await message.answer(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧\n\n⚙️ KONFIRMASI",
        reply_markup=kb.as_markup()
    )


# =========================
# DONE
# =========================
@router.callback_query(F.data == "done_upfile")
async def done(call: CallbackQuery, state: FSMContext):

    await save_file(call, state)


# =========================
# SAVE CORE + POST GROUP
# =========================
async def save_file(event, state: FSMContext, price=None):

    pool = await get_pool()
    bot: Bot = event.bot

    data = await state.get_data()

    media = data.get("media", [])
    if not media:
        await event.answer("❌ Tidak ada media")
        return

    file_id = media[0]
    media_count = len(media)

    file_type = data.get("type", "free")
    price = price if price is not None else data.get("price", 0)

    code = generate_code()
    user = event.from_user

    await pool.execute(
        """
        INSERT INTO files (
            code, file_id, owner_id,
            media_count, price, type, creator
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        """,
        code,
        file_id,
        user.id,
        media_count,
        price,
        file_type,
        user.full_name
    )

    await state.clear()

    text = f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧

📦 MEDIA SUCCESS SAVED

🔑 CODE : {code}
📊 MEDIA : {media_count}
💰 SYSTEM : {file_type.upper()} {price}
👤 CREATE : {user.full_name}
"""

    # update UI user (kalau pakai system UI)
    try:
        await event.message.edit_text(text)
    except:
        pass

    # post ke group
    try:
        await bot.send_message(CHANNEL_ID, text)
    except:
        pass

async def show_progress(message, total):
    for i in range(1, total + 1):

        text = f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

⏳ 𝗨𝗣𝗟𝗢𝗔𝗗𝗜𝗡𝗚 𝗣𝗥𝗢𝗖𝗘𝗦𝗦
────────────────
📊 𝗣𝗥𝗢𝗚𝗥𝗘𝗦𝗦 : {i}/{total}
"""

        await message.edit_text(text)
        await asyncio.sleep(0.25)
