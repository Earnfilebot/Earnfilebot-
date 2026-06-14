import asyncio
from math import ceil

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InputMediaPhoto
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_pool
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL

import httpx

router = Router()

# =========================
# STATE
# =========================
class GetFileState(StatesGroup):
    wait_code = State()


# =========================
# CACHE PAGE
# =========================
PAGE_CACHE = {}


# =========================
# BAYARGG INVOICE
# =========================
async def create_bayargg_invoice(amount: int, code: str, user_id: int):

    payload = {
        "amount": amount,
        "description": f"Purchase file {code}",
        "callback_url": "https://earnfilebot.up.railway.app/webhook/bayargg",
        "external_id": f"{user_id}_{code}"
    }

    headers = {
        "Authorization": f"Bearer {BAYARGG_API_KEY}"
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BAYARGG_BASE_URL}/transaction/create",
            json=payload,
            headers=headers
        )

    return r.json()


# =========================
# START GETFILE
# =========================
@router.callback_query(F.data == "getfile")
async def getfile_start(call: CallbackQuery, state: FSMContext):

    await state.clear()
    await state.set_state(GetFileState.wait_code)

    await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n🔑 KIRIM KODE FILE"
    )


# =========================
# CHECK PAID
# =========================
async def is_paid(user_id: int, code: str):

    pool = await get_pool()

    row = await pool.fetchrow(
        "SELECT * FROM payments WHERE user_id=$1 AND code=$2 AND status='paid'",
        user_id, code
    )

    return bool(row)


# =========================
# PAYMENT UI (BAYARGG)
# =========================
async def payment_ui(message: Message, file):

    invoice = await create_bayargg_invoice(
        amount=file["price"],
        code=file["code"],
        user_id=message.from_user.id
    )

    if not invoice.get("data"):
        await message.answer("❌ Gagal membuat invoice")
        return

    pay_url = invoice["data"]["checkout_url"]
    reference = invoice["data"]["reference"]

    pool = await get_pool()

    await pool.execute(
        """
        INSERT INTO payments (user_id, code, reference, status)
        VALUES ($1,$2,$3,'pending')
        """,
        message.from_user.id,
        file["code"],
        reference
    )

    await message.answer(
        f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

🔒 FILE LOCKED
────────────────
🔑 CODE : {file['code']}
💰 PRICE: Rp{file['price']}

💳 BAYARGG PAYMENT
👉 {pay_url}

⚡ Setelah bayar file akan otomatis unlock
"""
    )


# =========================
# BUILD MEDIA
# =========================
def build_media(file_id: str, caption=None):
    return InputMediaPhoto(
        media=file_id,
        caption=caption
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

    media_ids = file.get("media_ids") or [file["file_id"]]

    caption = f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

📦 FILE READY
────────────────
🔑 CODE  : {file['code']}
📊 MEDIA : {file['media_count']}
👤 OWNER : {file['creator']}
"""

    # =========================
    # FREE FILE
    # =========================
    if file["type"] == "free":

        group = []
        for i, fid in enumerate(media_ids):
            cap = caption if i == 0 else None
            group.append(build_media(fid, cap))

        await message.answer_media_group(group)
        await state.clear()
        return

    # =========================
    # PAID FILE
    # =========================

    paid = await is_paid(message.from_user.id, code)

    # ❌ belum bayar
    if not paid:
        await payment_ui(message, file)
        await state.clear()
        return

    # =========================
    # UNLOCK FILE
    # =========================
    group = []
    for i, fid in enumerate(media_ids):
        cap = f"{file['code']} • UNLOCKED" if i == 0 else None
        group.append(build_media(fid, cap))

    await message.answer_media_group(group)
    await state.clear()
