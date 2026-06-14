import asyncio
import httpx

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_pool
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL

router = Router()


# =========================
# STATE
# =========================
class GetFileState(StatesGroup):
    wait_code = State()


# =========================
# CREATE INVOICE
# =========================
async def create_invoice(amount: int, code: str, user_id: int):

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

    await state.set_state(GetFileState.wait_code)

    await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n🔑 KIRIM KODE FILE SEKARANG"
    )


# =========================
# CHECK PAID
# =========================
async def is_paid(user_id: int, code: str):

    pool = await get_pool()

    row = await pool.fetchrow(
        """
        SELECT 1 FROM payments
        WHERE user_id=$1 AND code=$2 AND status='paid'
        """,
        user_id,
        code
    )

    return bool(row)


# =========================
# PAYMENT UI
# =========================
async def payment_ui(message: Message, file):

    invoice = await create_invoice(
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
# MAIN GET FILE
# =========================
@router.message(GetFileState.wait_code)
async def receive_code(message: Message, state: FSMContext):

    print("GETFILE TRIGGERED:", message.text)

    if not message.text:
        await message.answer("❌ Kirim kode saja")
        return

    code = message.text.strip().upper()

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code=$1",
        code
    )

    if not file:
        await message.answer("❌ CODE TIDAK DITEMUKAN")
        await state.clear()
        return

    # =========================
    # AMBIL MEDIA (WAJIB ADA TYPE)
    # =========================
    media_list = file.get("media") or [
        {
            "file_id": file["file_id"],
            "file_type": "photo"
        }
    ]

    caption = f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

🔑 CODE  : {file['code']}
📦 MEDIA : {len(media_list)}
👤 OWNER : {file['creator']}
"""

    # =========================
    # FREE FILE
    # =========================
    if file["type"] == "free":

        group = []

        for i, m in enumerate(media_list):

            fid = m["file_id"]
            ftype = m.get("file_type", "photo")

            cap = caption if i == 0 else None

            if ftype == "video":
                group.append(InputMediaVideo(media=fid, caption=cap))

            elif ftype == "document":
                group.append(InputMediaDocument(media=fid, caption=cap))

            else:
                group.append(InputMediaPhoto(media=fid, caption=cap))

        await message.answer_media_group(group)
        await state.clear()
        return

    # =========================
    # PAID CHECK
    # =========================
    paid = await is_paid(message.from_user.id, code)

    if not paid:
        await payment_ui(message, file)
        await state.clear()
        return

    # =========================
    # UNLOCKED FILE
    # =========================
    group = []

    for i, m in enumerate(media_list):

        fid = m["file_id"]
        ftype = m.get("file_type", "photo")

        cap = f"{file['code']} • UNLOCKED" if i == 0 else None

        if ftype == "video":
            group.append(InputMediaVideo(media=fid, caption=cap))

        elif ftype == "document":
            group.append(InputMediaDocument(media=fid, caption=cap))

        else:
            group.append(InputMediaPhoto(media=fid, caption=cap))

    await message.answer_media_group(group)
    await state.clear()
