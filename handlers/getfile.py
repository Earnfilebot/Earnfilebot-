import asyncio
import json
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
# NORMALIZE TYPE (FIX WAJIB)
# =========================
def normalize_type(ftype: str, file_id: str) -> str:
    """
    Detect tipe file dari DB + fallback dari file_id Telegram
    """

    if ftype:
        ftype = ftype.lower()

        if ftype in ["photo", "image", "jpg", "jpeg", "png"]:
            return "photo"

        if ftype in ["video", "mp4", "mov"]:
            return "video"

        if ftype in ["doc", "document", "file", "pdf", "zip"]:
            return "document"

    # =========================
    # AUTO DETECT DARI FILE_ID
    # =========================
    if file_id.startswith("BAACAg"):  # biasanya document/video
        return "document"

    if file_id.startswith("BQACAg"):  # sering video
        return "video"

    if file_id.startswith("AgACAg"):  # photo
        return "photo"

    return "photo"
# =========================
# CREATE INVOICE
# =========================
async def create_invoice(amount: int, code: str, user_id: int):
    payload = {
        "amount": int(amount),
        "description": f"Purchase file {code}",
        "callback_url": "https://earnfilebot.up.railway.app/webhook/bayargg",
        "external_id": f"{user_id}_{code}"
    }

    headers = {
        "Authorization": f"Bearer {BAYARGG_API_KEY}"
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{BAYARGG_BASE_URL}/transaction/create",
                json=payload,
                headers=headers
            )

        data = r.json()
        print("INVOICE RESPONSE:", data)
        return data

    except Exception as e:
        print("INVOICE ERROR:", e)
        return {}


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

    data = invoice.get("data")
    if not data:
        await message.answer("❌ Gagal membuat invoice")
        return

    pay_url = data.get("checkout_url")
    reference = data.get("reference")

    if not pay_url or not reference:
        await message.answer("❌ Invoice invalid")
        return

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

💳 BAYAR:
👉 {pay_url}

⚡ Setelah bayar file otomatis unlock
"""
    )


# =========================
# MAIN GET FILE
# =========================
@router.message(GetFileState.wait_code)
async def receive_code(message: Message, state: FSMContext):
    try:
        if not message.text:
            await message.answer("❌ Kirim kode saja")
            return

        code = message.text.strip().upper()
        print("GETFILE:", code)

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
        # PARSE MEDIA
        # =========================
        raw_media = file.get("media")

        if isinstance(raw_media, str):
            try:
                raw_media = json.loads(raw_media)
            except:
                raw_media = []

        media_list = raw_media if isinstance(raw_media, list) else []

        if not media_list:
            media_list = [{
                "file_id": file.get("file_id")
            }]

        # =========================
        # BUILD MEDIA GROUP
        # =========================
        group = []

        caption = (
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n"
            f"🔑 CODE  : {file['code']}\n"
            f"📦 MEDIA : {len(media_list)}\n"
            f"👤 OWNER : {file['creator']}"
        )

        for i, m in enumerate(media_list):
            fid = m.get("file_id")

            # 🔥 FIX NESTED
            if isinstance(fid, dict):
                fid = fid.get("file_id")

            if not fid:
                continue

            cap = caption if i == 0 else None
            media_obj = None

            # 🔥 brute type
            try:
                media_obj = InputMediaVideo(media=fid, caption=cap)
            except:
                pass

            if not media_obj:
                try:
                    media_obj = InputMediaDocument(media=fid, caption=cap)
                except:
                    pass

            if not media_obj:
                try:
                    media_obj = InputMediaPhoto(media=fid, caption=cap)
                except:
                    pass

            if media_obj:
                group.append(media_obj)
            else:
                print("BUILD FAIL:", fid)

        if not group:
            await message.answer("❌ Media kosong / rusak")
            await state.clear()
            return

        # =========================
        # SAFE SEND
        # =========================
        async def safe_send():
            try:
                await message.answer_media_group(group)
                return True

            except Exception as e:
                print("GROUP SEND FAIL:", e)

                # fallback satu-satu
                for i, m in enumerate(media_list):
                    fid = m.get("file_id")

                    # 🔥 FIX NESTED LAGI
                    if isinstance(fid, dict):
                        fid = fid.get("file_id")

                    if not fid:
                        continue

                    cap = caption if i == 0 else None

                    try:
                        await message.answer_video(fid, caption=cap)
                        continue
                    except:
                        pass

                    try:
                        await message.answer_document(fid, caption=cap)
                        continue
                    except:
                        pass

                    try:
                        await message.answer_photo(fid, caption=cap)
                        continue
                    except Exception as err:
                        print("TOTAL SEND FAIL:", err)

                return False

        # =========================
        # FREE FILE
        # =========================
        if file["type"] == "free":
            await safe_send()
            await state.clear()
            return

        # =========================
        # CHECK PAYMENT
        # =========================
        paid = await is_paid(message.from_user.id, code)

        if not paid:
            await payment_ui(message, file)
            await state.clear()
            return

        # =========================
        # UNLOCKED
        # =========================
        group[0].caption = f"{file['code']} • UNLOCKED"

        await safe_send()
        await state.clear()

    except Exception as e:
        print("FATAL GETFILE ERROR:", e)
        await message.answer("❌ Terjadi error")
        await state.clear()
