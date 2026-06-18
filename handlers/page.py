import asyncio
import json
import time
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
# BUTTON BUILDER (FIXED WINDOW PAGINATION)
# =========================
def build_page_buttons(code: str, page: int, total: int):

    buttons = []

    # Prev
    buttons.append(
        InlineKeyboardButton(
            text="⬅️ Prev",
            callback_data=f"page:{code}:{max(1, page-1)}"
        )
    )

    # Window pagination (FIXED)
    start = max(1, page - 2)
    end = min(total, page + 2)

    for i in range(start, end + 1):

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

    # Next
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

    # =========================
    # SAFE PARSE
    # =========================
    try:
        _, code, page = call.data.split(":")
        page = int(page)
    except Exception:
        return await call.answer("❌ Invalid data", show_alert=True)

    # =========================
    # ANTI SPAM COOLDOWN
    # =========================
    now = time.time()
    if now - CLICK_COOLDOWN[call.from_user.id] < 0.5:
        return await call.answer("⏳ Slow down", show_alert=False)

    CLICK_COOLDOWN[call.from_user.id] = now

    # =========================
    # LOCK USER
    # =========================
    async with USER_LOCK[call.from_user.id]:

        await call.answer()  # jawab setelah validasi aman

        pool = await get_pool()

        file = await pool.fetchrow(
            "SELECT * FROM files WHERE code=$1",
            code
        )

        if not file:
            return await call.answer("❌ File not found", show_alert=True)

        # =========================
        # ACCESS CHECK (FIXED)
        # =========================
        try:
            price = int(file.get("price") or 0)
        except Exception:
            price = 0

        if price > 0:
            access = await pool.fetchval(
                """
                SELECT 1
                FROM user_access
                WHERE user_id=$1
                AND code=$2
                AND paid=true
                """,
                call.from_user.id,
                code
            )

            if not access:
                return await call.answer(
                    "🔒 Anda belum membeli file ini",
                    show_alert=True
                )

        # =========================
        # MEDIA PARSE SAFE
        # =========================
        media = file.get("media") or []

        if isinstance(media, str):
            try:
                media = json.loads(media)
            except Exception:
                media = []

        if not isinstance(media, list) or not media:
            return await call.message.answer("❌ File kosong")

        # =========================
        # PAGE SAFE LIMIT
        # =========================
        total_page = max(1, (len(media) + PAGE_SIZE - 1) // PAGE_SIZE)

        page = max(1, min(page, total_page))

        chunk = media[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]

        if not chunk:
            return await call.message.answer("❌ Page kosong")

        # =========================
        # CAPTION
        # =========================
        caption = (
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫 𝗙𝗜𝗟𝗘\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"🔑 CODE : {code}\n"
            f"📦 PAGE : {page}/{total_page}\n"
            f"📊 TOTAL : {len(media)} FILE"
        )

        # =========================
        # BUILD MEDIA GROUP (SAFE)
        # =========================
        group = []

        for m in chunk:

            if not isinstance(m, dict):
                continue

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

        if not group:
            return await call.message.answer("❌ Tidak ada media valid")

        # =========================
        # DELETE OLD MESSAGE SAFE
        # =========================
        try:
            await call.message.delete()
        except Exception:
            pass

        # =========================
        # SEND MEDIA SAFE (FIX TELEGRAM LIMIT)
        # =========================
        if len(group) == 1:
            only = group[0]

            if isinstance(only, InputMediaPhoto):
                await call.message.answer_photo(only.media)
            elif isinstance(only, InputMediaVideo):
                await call.message.answer_video(only.media)
            else:
                await call.message.answer_document(only.media)
        else:
            await call.message.answer_media_group(group)

        # =========================
        # BUTTON
        # =========================
        nav = build_page_buttons(code, page, total_page)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                nav,
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

        await call.message.answer(caption, reply_markup=keyboard)
