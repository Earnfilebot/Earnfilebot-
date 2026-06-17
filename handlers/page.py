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
            try:
                media = json.loads(media)
            except:
                media = []

        if not isinstance(media, list):
            media = []

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
        # TAKE FIRST MEDIA ONLY (IMPORTANT)
        # =========================
        first = chunk[0]
        fid = clean_file_id(first.get("file_id"))
        ftype = normalize_type(first.get("type"))

        if not fid:
            return await call.answer("❌ Media invalid", show_alert=True)

        # =========================
        # KEYBOARD
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
        # SAFE EDIT (ONLY THIS WAY)
        # =========================
        try:
            if ftype == "photo":
                await call.message.edit_media(
                    media=InputMediaPhoto(media=fid, caption=caption),
                    reply_markup=keyboard
                )

            elif ftype == "video":
                await call.message.edit_media(
                    media=InputMediaVideo(media=fid, caption=caption),
                    reply_markup=keyboard
                )

            else:
                await call.message.edit_media(
                    media=InputMediaDocument(media=fid, caption=caption),
                    reply_markup=keyboard
                )

        except:
            await call.message.edit_text(
                caption,
                reply_markup=keyboard
            )

        await call.answer()
