import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InputMediaVideo, InputMediaDocument
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
# START GETFILE
# =========================
@router.callback_query(F.data == "getfile")
async def getfile_start(call: CallbackQuery, state: FSMContext):

    await state.clear()
    await state.set_state(GetFileState.wait_code)

    await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n🔑 KIRIM KODE FILE SEKARANG\n\nContoh: EF_ABC123XYZ"
    )


# =========================
# BUILD MEDIA WITH WATERMARK
# =========================
def build_media(file_id: str, caption: str, media_type: str):

    caption = f"{caption}\n\n𝗪𝗔𝗧𝗘𝗥𝗠𝗔𝗥𝗞 • EARNFILEBOT"

    if media_type == "photo":
        return InputMediaPhoto(media=file_id, caption=caption)

    if media_type == "video":
        return InputMediaVideo(media=file_id, caption=caption)

    return InputMediaDocument(media=file_id, caption=caption)


# =========================
# SEND MEDIA GROUP (WITH PAGINATION SUPPORT)
# =========================
async def send_media_group(message, media_ids, caption_base):

    group = []

    for i, file_id in enumerate(media_ids):
        if i == 0:
            cap = caption_base
        else:
            cap = None

        group.append(InputMediaPhoto(media=file_id, caption=cap))

    await message.answer_media_group(group)


# =========================
# PAGINATION STATE CACHE
# =========================
PAGE_CACHE = {}


def build_page_keyboard(code, page, total_pages):

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()

    if page > 1:
        kb.button(text="⬅️ Prev", callback_data=f"page_{code}_{page-1}")

    kb.button(text=f"{page}/{total_pages}", callback_data="noop")

    if page < total_pages:
        kb.button(text="Next ➡️", callback_data=f"page_{code}_{page+1}")

    kb.adjust(3)
    return kb.as_markup()


# =========================
# PAGE HANDLER
# =========================
@router.callback_query(F.data.startswith("page_"))
async def paginate(call: CallbackQuery):

    _, code, page = call.data.split("_")
    page = int(page)

    data = PAGE_CACHE.get(code)

    if not data:
        await call.answer("Data expired", show_alert=True)
        return

    media = data["media"]
    chunk_size = 10

    chunks = [media[i:i+chunk_size] for i in range(0, len(media), chunk_size)]

    if page < 1 or page > len(chunks):
        return

    chunk = chunks[page-1]

    group = []
    for i, file_id in enumerate(chunk):
        cap = data["caption"] if i == 0 else None
        group.append(InputMediaPhoto(media=file_id, caption=cap))

    await call.message.delete()

    await call.message.answer_media_group(group)


# =========================
# GET FILE MAIN
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
        await message.answer(
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n❌ CODE TIDAK DITEMUKAN"
        )
        return

    media_ids = file["media_ids"] if file["media_ids"] else [file["file_id"]]

    caption = f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

📦 FILE READY
────────────────
🔑 CODE  : {file['code']}
📊 MEDIA : {file['media_count']}
👤 OWNER : {file['creator']}

━━━━━━━━━━━━━━━━
𝗪𝗔𝗧𝗘𝗥𝗠𝗔𝗥𝗞 • EARNFILEBOT
"""

    # =========================
    # FREE FILE
    # =========================
    if file["type"] == "free":

        # simpan cache untuk pagination
        PAGE_CACHE[code] = {
            "media": media_ids,
            "caption": caption
        }

        if len(media_ids) <= 10:
            group = []

            for i, fid in enumerate(media_ids):
                cap = caption if i == 0 else None
                group.append(InputMediaPhoto(media=fid, caption=cap))

            await message.answer_media_group(group)

        else:
            # kirim page 1
            page = 1
            chunk = media_ids[:10]

            group = []
            for i, fid in enumerate(chunk):
                cap = caption if i == 0 else None
                group.append(InputMediaPhoto(media=fid, caption=cap))

            await message.answer_media_group(group)

            kb = build_page_keyboard(code, page, (len(media_ids) // 10) + 1)

            await message.answer(
                "📦 MEDIA LEBIH DARI 10 - GUNAKAN NAVIGASI",
                reply_markup=kb
            )

        await state.clear()
        return

    # =========================
    # PAID FILE
    # =========================
    await message.answer(
        f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

🔒 PAID FILE
────────────────
🔑 CODE  : {file['code']}
💰 PRICE : Rp{file['price']}
👤 OWNER : {file['creator']}

━━━━━━━━━━━━━━━━
❌ PERLU PEMBAYARAN UNTUK DOWNLOAD
"""
    )

    await state.clear()
