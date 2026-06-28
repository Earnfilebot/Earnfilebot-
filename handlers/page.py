import asyncio
import json
import time
from collections import defaultdict

from aiogram import Router, F

from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument
)

from database import get_pool

router = Router()

PAGE_SIZE = 10

CLICK_COOLDOWN = defaultdict(float)
USER_LOCK = defaultdict(lambda: asyncio.Lock())
USER_PAGE_LOCK = defaultdict(float)

# =========================
# UTIL
# =========================
def clean_file_id(fid):
    if isinstance(fid, dict):
        return fid.get("file_id")
    return fid


def normalize_type(ftype):
    if not ftype:
        return "document"
    return ftype.lower()


# =========================
# BUTTON BUILDER
# =========================
def build_page_buttons(code: str, page: int, total: int):

    row = []

    row.append(
        InlineKeyboardButton(
            text="⬅️ Prev",
            callback_data=f"page:{code}:{max(1, page - 1)}"
        )
    )

    start = max(1, page - 2)
    end = min(total, page + 2)

    for i in range(start, end + 1):
        emoji = "🟡" if i == page else ("🟢" if i < page else "🔴")

        row.append(
            InlineKeyboardButton(
                text=f"{i}{emoji}",
                callback_data=f"page:{code}:{i}"
            )
        )

    row.append(
        InlineKeyboardButton(
            text="Next ➡️",
            callback_data=f"page:{code}:{min(total, page + 1)}"
        )
    )

    return row


# =========================
# HANDLER
# =========================
@router.callback_query(F.data.startswith("page:"))
async def page_handler(call: CallbackQuery):

    user_id = call.from_user.id

    try:
        _, code, page = call.data.split(":")
        page = int(page)
    except Exception:
        return await call.answer("❌ Invalid data", show_alert=True)

    now = time.time()

    # =========================
    # ⏳ GLOBAL COOLDOWN 15 DETIK
    # =========================
    CLICK_KEY = f"{user_id}:{code}:{page}"

    if now - CLICK_COOLDOWN[CLICK_KEY] < 2:
       return await call.answer("⏳ terlalu cepat", show_alert=True)
    
    CLICK_COOLDOWN[CLICK_KEY] = now
    # =========================
    # 🔒 24 JAM LOCK PER PAGE
    # =========================
    page_key = f"{user_id}:{code}:{page}"

    last_open = USER_PAGE_LOCK.get(page_key)

    if last_open:
        if now - last_open < 86400:  # 24 jam
            return await call.answer(
                "⛔ Page ini sudah dibuka, tunggu 24 jam",
                show_alert=True
            )

    USER_PAGE_LOCK[page_key] = now

    async with USER_LOCK[user_id]:

        pool = await get_pool()

        file = await pool.fetchrow(
            "SELECT * FROM files WHERE code=$1",
            code
        )

        if not file:
            return await call.answer("❌ File tidak ditemukan", show_alert=True)

        media = file.get("media")

        if isinstance(media, str):
            try:
                media = json.loads(media)
            except:
                media = []

        if not isinstance(media, list) or not media:
            return await call.answer("❌ File kosong", show_alert=True)

        total_page = max(1, (len(media) + PAGE_SIZE - 1) // PAGE_SIZE)

        if page < 1:
            page = 1

        if page > total_page:
            return await call.answer("📦 Media sudah habis", show_alert=True)

        chunk = media[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]

        caption = (
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"🔑 CODE : {code}\n"
            f"📦 PAGE : {page}/{total_page}\n"
            f"📊 TOTAL : {len(media)} FILE"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                build_page_buttons(code, page, total_page),
                [
                    InlineKeyboardButton(
                        text="📢 Channel Update",
                        url="https://t.me/+F6-XB1gFA9VhMDc1"
                    ),
                    InlineKeyboardButton(
                        text="🔔 Notifikasi Code",
                        url="https://t.me/+VebkFndPTeFkMGU1"
                    )
                ]
            ]
        )

        album = []

        for i, item in enumerate(chunk):

            fid = item.get("file_id")
            ftype = (item.get("type") or "document").lower()

            if not fid:
                continue

            cap = caption if i == 0 else None

            if ftype == "photo":
                album.append(InputMediaPhoto(media=fid, caption=cap))

            elif ftype == "video":
                album.append(InputMediaVideo(media=fid, caption=cap))

            else:
                album.append(InputMediaDocument(media=fid, caption=cap))

        if not album:
            return await call.answer("❌ Tidak ada media valid", show_alert=True)

        try:
            await call.message.answer_media_group(media=album)

            await call.message.answer(
                "📦 NAVIGATION",
                reply_markup=keyboard
            )

        except Exception as e:
            return await call.answer(f"❌ {str(e)}", show_alert=True)

        await call.answer()
