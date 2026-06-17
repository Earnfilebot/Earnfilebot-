import asyncio
import json
from collections import defaultdict

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from database import get_pool

router = Router()

PAGE_SIZE = 10

CLICK_COOLDOWN = defaultdict(float)
USER_LOCK = defaultdict(asyncio.Lock)

PAGE_CACHE = {}


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
    ftype = ftype.lower()
    if ftype == "photo":
        return "photo"
    if ftype == "video":
        return "video"
    return "document"


# =========================
# BUTTON BUILDER (🔴🟡🟢 FIXED)
# =========================
def build_page_buttons(code: str, page: int, total: int):

    buttons = []

    # PREV
    buttons.append(
        InlineKeyboardButton(
            text="⬅️ Prev",
            callback_data=f"page:{code}:{max(1, page-1)}"
        )
    )

    # PAGE INDICATOR
    for i in range(1, min(total, 5) + 1):

        if i < page:
            emoji = "🟢"
        elif i == page:
            emoji = "🟡"
        else:
            emoji = "🔴"

        buttons.append(
            InlineKeyboardButton(
                text=f"{i}{emoji}",
                callback_data=f"page:{code}:{i}"
            )
        )

    # NEXT
    buttons.append(
        InlineKeyboardButton(
            text="Next ➡️",
            callback_data=f"page:{code}:{min(total, page+1)}"
        )
    )

    return buttons


# =========================
# MAIN HANDLER
# =========================
@router.callback_query(F.data.startswith("page:"))
async def page_handler(call: CallbackQuery):

    try:
        _, code, page = call.data.split(":")
        page = int(page)
    except:
        return await call.answer("❌ Invalid data", show_alert=True)

    async with USER_LOCK[call.from_user.id]:

        pool = await get_pool()

        file = await pool.fetchrow(
            "SELECT * FROM files WHERE code=$1",
            code
        )

        if not file:
            return await call.answer("❌ File tidak ditemukan", show_alert=True)

        media = file.get("media") or []

        if isinstance(media, str):
            media = json.loads(media)

        total_page = max(1, (len(media) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(1, min(page, total_page))

        chunk = media[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]

        if not chunk:
            return await call.answer("❌ Page kosong", show_alert=True)

        caption = (
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫 𝗙𝗜𝗟𝗘\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"🔑 CODE : {code}\n"
            f"📦 PAGE : {page}/{total_page}\n"
            f"📊 TOTAL : {len(media)} FILE"
        )

        # =========================
        # BUILD MEDIA GROUP (FIXED)
        # =========================
        group = []

        for m in chunk:
            fid = clean_file_id(m.get("file_id"))
            ftype = normalize_type(m.get("type"))

            if not fid:
                continue

            if ftype == "photo":
                group.append(InputMediaPhoto(media=fid))
            elif ftype == "video":
                group.append(InputMediaVideo(media=fid))
            else:
                group.append(InputMediaDocument(media=fid))

        # =========================
        # KEYBOARD (AUTO REFRESH)
        # =========================
        nav = build_page_buttons(code, page, total_page)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            nav,
            [
                InlineKeyboardButton(
                    text="📢 Channel Update",
                    url="https://t.me/yourchannel"
                ),
                InlineKeyboardButton(
                    text="🔔 Notifikasi Code",
                    callback_data=f"notify:{code}"
                )
            ]
        ])

        # =========================
        # IMPORTANT: DELETE OLD MESSAGE
        # =========================
        try:
            await call.message.delete()
        except:
            pass

        # =========================
        # SEND NEW MEDIA GROUP (PAGE)
        # =========================
        sent = await call.message.answer_media_group(group)

        # =========================
        # SEND CAPTION + BUTTONS (SEPARATE MESSAGE)
        # =========================
        await call.message.answer(
            caption,
            reply_markup=keyboard
        )

        await call.answer()
