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

    # Cari dari link start
    m = re.search(
        r"getFile_([A-Za-z0-9_-]+)",
        text,
        re.IGNORECASE
    )
    if m:
        code = m.group(1)

    # Cari dari "Code : xxx"
    if not code:
        m = re.search(
            r"code\s*[:：]\s*([A-Za-z0-9_-]+)",
            text,
            re.IGNORECASE
        )
        if m:
            code = m.group(1)

    # Cari kode langsung di dalam teks
    if not code:
        m = re.search(
            r"(DecoderFileBot[A-Za-z0-9_-]+)",
            text
        )
        if m:
            code = m.group(1)

    # Kalau tetap tidak ketemu, anggap seluruh pesan adalah kode
    if not code:
        code = text

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
    # MEDIA
    # =========================
    media = safe_json(file.get("media"))

    if not media:
        await message.answer("❌ FILE KOSONG")
        await state.clear()
        return

    first = get_first_media(media)

    if not first or not first.get("file_id"):
        await message.answer("❌ FILE INVALID")
        await state.clear()
        return

    fid = first["file_id"]
    ftype = (first.get("type") or "document").lower()

    # =========================
    # SHARE MODE
    # =========================
    share_media = file.get("share_media", True)
    share_status = "PUBLIC" if share_media else "PRIVATE"

    # =========================
    # BUTTON
    # =========================
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
            await message.answer_photo(
                fid,
                caption=caption,
                reply_markup=keyboard
            )

        elif ftype == "video":
            await message.answer_video(
                fid,
                caption=caption,
                reply_markup=keyboard
            )

        else:
            await message.answer_document(
                fid,
                caption=caption,
                reply_markup=keyboard
            )

    except Exception as e:
        await message.answer(f"❌ MEDIA ERROR:\n{e}")

    await state.clear()
