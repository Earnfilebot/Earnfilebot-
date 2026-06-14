import random
import string

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_pool

CHANNEL_ID = -1003721009353

router = Router()


# =========================
# STATE
# =========================
class UploadState(StatesGroup):
    wait_type = State()
    wait_price = State()


# =========================
# CODE GENERATOR (AMAN)
# =========================
def generate_code():
    return "EF_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=16))


# =========================
# STEP 1 - RECEIVE MEDIA
# =========================
@router.message(F.document | F.video | F.photo)
async def receive_media(message: Message, state: FSMContext):

    data = await state.get_data()
    media = data.get("media", [])

    if message.document:
        file_id = message.document.file_id
    elif message.video:
        file_id = message.video.file_id
    else:
        file_id = message.photo[-1].file_id

    media.append(file_id)
    await state.update_data(media=media)

    kb = InlineKeyboardBuilder()
    kb.button(text="💾 SAVE", callback_data="save_upfile")
    kb.button(text="❌ CANCEL", callback_data="cancel_upfile")
    kb.adjust(2)

    await message.answer(
        f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧

📦 𝗠𝗘𝗗𝗜𝗔 𝗥𝗘𝗖𝗘𝗜𝗩𝗘𝗗
📊 𝗖𝗢𝗨𝗡𝗧 : {len(media)}
""",
        reply_markup=kb.as_markup()
    )


# =========================
# CANCEL → HOME
# =========================
@router.callback_query(F.data == "cancel_upfile")
async def cancel(call: CallbackQuery, state: FSMContext):

    await state.clear()

    await call.answer("Upload dibatalkan", show_alert=True)

    await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧\n\n❌ 𝗨𝗣𝗟𝗢𝗔𝗗 𝗖𝗔𝗡𝗖𝗘𝗟𝗟𝗘𝗗"
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
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧\n\n📦 𝗖𝗛𝗢𝗢𝗦𝗘 𝗧𝗬𝗣𝗘",
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
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧\n\n💰 𝗜𝗡𝗣𝗨𝗧 𝗣𝗥𝗜𝗖𝗘\nContoh: 10000 / 10.000"
        )
    else:
        await save_file(call, state, price=0)


# =========================
# PRICE INPUT
# =========================
@router.message(UploadState.wait_price)
async def input_price(message: Message, state: FSMContext):

    raw = message.text.replace(".", "").replace(",", "")

    if not raw.isdigit():
        await message.answer("❌ Format salah (10000 / 10.000)")
        return

    price = int(raw)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ DONE", callback_data="done_upfile")
    kb.button(text="❌ CANCEL", callback_data="cancel_upfile")
    kb.adjust(2)

    await state.update_data(price=price)

    await message.answer(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧\n\n⚙️ 𝗖𝗢𝗡𝗙𝗜𝗥𝗠 𝗦𝗔𝗩𝗘",
        reply_markup=kb.as_markup()
    )


# =========================
# DONE
# =========================
@router.callback_query(F.data == "done_upfile")
async def done(call: CallbackQuery, state: FSMContext):

    await save_file(call, state)


# =========================
# SAVE CORE (DB + GROUP POST)
# =========================
async def save_file(event, state: FSMContext, price=None):

    pool = await get_pool()
    bot: Bot = event.bot

    data = await state.get_data()

    media = data.get("media", [])
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

📦 𝗠𝗘𝗗𝗜𝗔 𝗦𝗨𝗖𝗖𝗘𝗦 𝗦𝗔𝗩𝗘𝗗

🔑 𝗖𝗢𝗗𝗘 : {code}
📊 𝗠𝗘𝗗𝗜𝗔 : {media_count}
💰 𝗦𝗬𝗦𝗧𝗘𝗠 : {file_type.upper()} {price}
👤 𝗖𝗥𝗘𝗔𝗧𝗘 : {user.full_name}

━━━━━━━━━━━━━━
𝗖𝗢𝗣𝗬𝗥𝗜𝗚𝗛𝗧 𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧
"""

    # user
    await event.message.edit_text(text)

    # group post (SAFE)
    try:
        await bot.send_message(CHANNEL_ID, text)
    except:
        pass
