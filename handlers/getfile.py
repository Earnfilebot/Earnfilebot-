import asyncio
from math import ceil

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InputMediaPhoto, InputMediaVideo, InputMediaDocument
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_pool

router = Router()

PAGE_CACHE = {}


class GetFileState(StatesGroup):
    wait_code = State()


# =========================
# GET FILE START
# =========================
@router.callback_query(F.data == "getfile")
async def getfile_start(call: CallbackQuery, state: FSMContext):

    await state.clear()
    await state.set_state(GetFileState.wait_code)

    await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n🔑 KIRIM KODE FILE"
    )


# =========================
# CHECK USER PURCHASE
# =========================
async def is_paid(user_id: int, code: str):

    pool = await get_pool()

    row = await pool.fetchrow(
        "SELECT * FROM purchases WHERE user_id=$1 AND code=$2 AND status='paid'",
        user_id,
        code
    )

    return bool(row)


# =========================
# PAYMENT MENU
# =========================
async def payment_ui(message: Message, file):

    text = f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

🔒 FILE LOCKED
────────────────
🔑 CODE : {file['code']}
💰 PRICE: Rp{file['price']}

━━━━━━━━━━━━━━━━
💳 PAYMENT REQUIRED
"""

    kb = [
        [
            {"text": "💳 PAY NOW", "callback_data": f"pay:{file['code']}"}
        ]
    ]

    await message.answer(text, reply_markup={"inline_keyboard": kb})


# =========================
# PAYMENT CLICK
# =========================
@router.callback_query(F.data.startswith("pay:"))
async def pay(call: CallbackQuery):

    code = call.data.split(":")[1]
    user_id = call.from_user.id

    pool = await get_pool()

    await pool.execute(
        """
        INSERT INTO purchases (user_id, code, status)
        VALUES ($1,$2,'pending')
        ON CONFLICT DO NOTHING
        """,
        user_id,
        code
    )

    await call.message.edit_text(
        f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

💳 PAYMENT INSTRUCTION
────────────────
🔑 CODE : {code}

📌 TRANSFER VIA:
- QRIS / DANA / GOPAY

📩 Setelah bayar, admin akan approve
"""
    )


# =========================
# MAIN GET FILE
# =========================
@router.message(GetFileState.wait_code)
async def get_file(message: Message, state: FSMContext):

    code = message.text.strip()
    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code = $1",
        code
    )

    if not file:
        await message.answer("❌ CODE TIDAK DITEMUKAN")
        return

    # =========================
    # FREE FILE
    # =========================
    if file["type"] == "free":

        media_ids = file.get("media_ids") or [file["file_id"]]
        media_types = file.get("media_types") or ["photo"] * len(media_ids)

        group = []
        for i, fid in enumerate(media_ids):
            cap = file["code"] if i == 0 else None
            group.append(InputMediaPhoto(media=fid, caption=cap))

        await message.answer_media_group(group)
        await state.clear()
        return

    # =========================
    # PAID FILE → CHECK PAYMENT
    # =========================
    paid = await is_paid(message.from_user.id, code)

    if not paid:
        await payment_ui(message, file)
        await state.clear()
        return

    # =========================
    # UNLOCKED FILE
    # =========================
    media_ids = file.get("media_ids") or [file["file_id"]]

    group = []
    for i, fid in enumerate(media_ids):
        cap = f"{file['code']} • UNLOCKED" if i == 0 else None
        group.append(InputMediaPhoto(media=fid, caption=cap))

    await message.answer_media_group(group)
    await state.clear()
