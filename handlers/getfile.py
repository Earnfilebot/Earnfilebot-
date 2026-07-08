import json

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_pool

router = Router()


# =========================
# STATE
# =========================
class GetFileState(StatesGroup):
    wait_code = State()


# =========================
# UTIL
# =========================
def safe_json(data):
    if isinstance(data, str):
        try:
            return json.loads(data)
        except:
            return []
    return data or []


def get_first_media(media):
    return media[0] if isinstance(media, list) and media else None


# =========================
# START
# =========================
@router.callback_query(F.data == "getfile")
async def getfile_start(call: CallbackQuery, state: FSMContext):

    await state.set_state(GetFileState.wait_code)

    await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n🔑 KIRIM KODE FILE"
    )

    await call.answer()


# =========================
# RECEIVE CODE
# =========================
@router.message(GetFileState.wait_code)
async def receive_code(message: Message, state: FSMContext):

    if not message.text:
        return await message.answer("❌ Kode kosong")

    import re

    text = message.text.strip()
    code = None

    m = re.search(r"getFile_([A-Za-z0-9_-]+)", text, re.IGNORECASE)
    if m:
        code = m.group(1)

    if not code:
        m = re.search(r"code\s*[:：]\s*([A-Za-z0-9_-]+)", text, re.IGNORECASE)
        if m:
            code = m.group(1)

    if not code:
        m = re.search(r"(DecoderFileBot[A-Za-z0-9_-]+)", text)
        if m:
            code = m.group(1)

    if not code:
        code = text

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code=$1",
        code
    )

    # =========================
    # FILE NOT FOUND
    # =========================
    if not file:
        await message.answer("❌ CODE TIDAK DITEMUKAN")
        await state.clear()
        return

    # =========================
    # EXPIRED CHECK
    # =========================
    import time

    expires_at = file["expires_at"]

    if expires_at and expires_at < int(time.time()):
        await message.answer("❌ File sudah kadaluarsa.")
        await state.clear()
        return

    # =========================
    # VIEW COUNTER
    # =========================
    await pool.execute(
        """
        UPDATE files
        SET view_count = view_count + 1
        WHERE code=$1
        """,
        code
    )

    media = safe_json(file["media"])

    if not media:
        await message.answer("❌ FILE KOSONG")
        await state.clear()
        return

    # =========================
    # FILE PAID CHECK
    # =========================
    is_paid = file["is_paid"] or False
    price = file["price"] or 0

    vip = await pool.fetchval(
        """
        SELECT 1
        FROM users
        WHERE id=$1
          AND vip=TRUE
          AND vip_until > NOW()
        """,
        message.from_user.id
    )

    owner = message.from_user.id == file["owner_id"]

    access = await pool.fetchval(
        """
        SELECT 1
        FROM file_purchases
        WHERE user_id=$1
          AND file_code=$2
          AND status='paid'
        """,
        message.from_user.id,
        code
    )

    has_access = bool(vip or owner or access)

    # =========================
    # BLOCK PAID FILE
    # =========================
    if is_paid and not has_access:

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"💳 BAYAR Rp {price:,}".replace(",", "."),
                        callback_data=f"pay:{code}"
                    )
                ]
            ]
        )

        text = (
            "🔒 FILE BERBAYAR\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"🔑 CODE  : {code}\n\n"
            f"💰 HARGA : Rp {price:,}\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ Silakan lakukan pembayaran untuk membuka file."
        ).replace(",", ".")

        await message.answer(text, reply_markup=keyboard)
        await state.clear()
        return

    # =========================
    # FREE / VIP / OWNER ACCESS
    # =========================
    first = get_first_media(media)

    if not first or not first.get("file_id"):
        await message.answer("❌ FILE INVALID")
        await state.clear()
        return

    fid = first["file_id"]
    ftype = (first.get("type") or "document").lower()

    share_media = file["share_media"] if file["share_media"] is not None else True
    share_status = "PUBLIC" if share_media else "PRIVATE"
    protect = not share_media

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📂 OPEN FILE",
                    callback_data=f"page:{code}:1"
                )
            ]
        ]
    )

    caption = (
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
        f"🔑 CODE: {code}\n"
        f"📊 FILE: {len(media)}\n"
        f"📤 SHARE: {share_status}"
    )

    try:
        if ftype == "photo":
            await message.answer_photo(fid, caption=caption, reply_markup=keyboard, protect_content=protect)

        elif ftype == "video":
            await message.answer_video(fid, caption=caption, reply_markup=keyboard, protect_content=protect)

        else:
            await message.answer_document(fid, caption=caption, reply_markup=keyboard, protect_content=protect)

    except Exception as e:
        await message.answer(f"❌ MEDIA ERROR:\n{e}")

    await state.clear()
