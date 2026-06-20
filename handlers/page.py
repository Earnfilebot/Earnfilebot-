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
# BUTTON BUILDER (FIXED ROW STRUCTURE)
# =========================
def build_page_buttons(code: str, page: int, total: int):

    row = []

    # Prev
    row.append(
        InlineKeyboardButton(
            text="⬅️ Prev",
            callback_data=f"page:{code}:{max(1, page-1)}"
        )
    )

    # Pagination window
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

    # Next
    row.append(
        InlineKeyboardButton(
            text="Next ➡️",
            callback_data=f"page:{code}:{min(total, page+1)}"
        )
    )

    return row


# =========================
# MAIN HANDLER
# =========================
@router.callback_query(F.data.startswith("page:"))
async def page_handler(call: CallbackQuery):

    user_id = call.from_user.id

    # =========================
    # SAFE PARSE
    # =========================
    try:
        _, code, page = call.data.split(":")
        page = int(page)
    except:
        return await call.answer("❌ Invalid data", show_alert=True)

    # =========================
    # ANTI SPAM
    # =========================
    now = time.time()

    if now - CLICK_COOLDOWN[user_id] < 0.5:
        return await call.answer("⏳ Slow down")

    CLICK_COOLDOWN[user_id] = now

    # =========================
    # LOCK USER
    # =========================
    async with USER_LOCK[user_id]:

        pool = await get_pool()

        file = await pool.fetchrow(
            "SELECT * FROM files WHERE code=$1",
            code
        )

        if not file:
            return await call.answer("❌ File not found", show_alert=True)

        # =========================
        # ACCESS CHECK
        # =========================
        price = int(file.get("price") or 0)

        if price > 0:
            access = await pool.fetchval(
                """
                SELECT 1 FROM user_access
                WHERE user_id=$1 AND code=$2 AND paid=true
                """,
                user_id,
                code
            )

            if not access:
                return await call.answer(
                    "🔒 Anda belum membeli file ini",
                    show_alert=True
                )

        # =========================
        # MEDIA PARSE
        # =========================
        media = file.get("media") or []

        if isinstance(media, str):
            try:
                media = json.loads(media)
            except:
                media = []

        if not media:
            return await call.answer("❌ File kosong", show_alert=True)

        # =========================
        # PAGE CALC
        # =========================
        total_page = max(1, (len(media) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(1, min(page, total_page))

        chunk = media[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]

        # =========================
        # BUILD MEDIA GROUP (ONLY IF MULTI)
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
            return await call.answer("❌ Media kosong", show_alert=True)

        # =========================
        # CAPTION
        # =========================
        caption = (
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"🔑 CODE : {code}\n"
            f"📦 PAGE : {page}/{total_page}\n"
            f"📊 TOTAL : {len(media)} FILE"
        )

        # =========================
        # KEYBOARD (FIXED)
        # =========================
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                build_page_buttons(code, page, total_page),
                [
                    InlineKeyboardButton("📢 Channel Update", url="https://t.me/+F6-XB1gFA9VhMDc1"),
                    InlineKeyboardButton("🔔 Notifikasi Code", url="https://t.me/+VebkFndPTeFkMGU1")
                ]
            ]
        )

        # =========================
        # EDIT MESSAGE ONLY (NO SPAWN SPAM)
        # =========================
        try:
            await call.message.edit_caption(
                caption=caption,
                reply_markup=keyboard
            )
        except:
            try:
                await call.message.edit_text(
                    caption,
                    reply_markup=keyboard
                )
            except:
                await call.answer("❌ Gagal update message", show_alert=True)

        # =========================
        # MEDIA SAFE SEND (ONLY FIRST PAGE STYLE FIX)
        # =========================
        # NOTE: ini cuma kirim preview biar tidak spam chat
        only = group[0]

        if isinstance(only, InputMediaPhoto):
            await call.message.answer_photo(only.media)
        elif isinstance(only, InputMediaVideo):
            await call.message.answer_video(only.media)
        else:
            await call.message.answer_document(only.media)
