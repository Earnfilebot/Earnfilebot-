import asyncio
import json
import time
from collections import defaultdict

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.exceptions import TelegramBadRequest

from database import get_pool

router = Router()

PAGE_SIZE = 10

CLICK_COOLDOWN = defaultdict(float)
USER_LOCK = defaultdict(lambda: asyncio.Lock())


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

        if i == page:
            emoji = "🟡"
        elif i < page:
            emoji = "🟢"
        else:
            emoji = "🔴"

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
# PAGE HANDLER
# =========================
@router.callback_query(F.data.startswith("page:"))
async def page_handler(call: CallbackQuery):

    user_id = call.from_user.id

    try:
        _, code, page = call.data.split(":")
        page = int(page)

    except Exception:
        return await call.answer(
            "❌ Invalid data",
            show_alert=True
        )

    now = time.time()

    if now - CLICK_COOLDOWN[user_id] < 0.5:
        return await call.answer("⏳ Slow down")

    CLICK_COOLDOWN[user_id] = now

    async with USER_LOCK[user_id]:

        pool = await get_pool()

        file = await pool.fetchrow(
            """
            SELECT *
            FROM files
            WHERE code = $1
            """,
            code
        )

        if not file:
            return await call.answer(
                "❌ File tidak ditemukan",
                show_alert=True
            )

        price = int(file.get("price") or 0)

        if price > 0:

            access = await pool.fetchval(
                """
                SELECT 1
                FROM user_access
                WHERE user_id = $1
                AND code = $2
                AND paid = true
                """,
                user_id,
                code
            )

            if not access:
                return await call.answer(
                    "🔒 Anda belum membeli file ini",
                    show_alert=True
                )

        media = file.get("media") or []

        if isinstance(media, str):
            try:
                media = json.loads(media)
            except Exception:
                media = []

        if not media:
            return await call.answer(
                "❌ File kosong",
                show_alert=True
            )

        total_page = max(
            1,
            (len(media) + PAGE_SIZE - 1) // PAGE_SIZE
        )

        page = max(
            1,
            min(page, total_page)
        )

        caption = (
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"🔑 CODE : {code}\n"
            f"📦 PAGE : {page}/{total_page}\n"
            f"📊 TOTAL : {len(media)} FILE"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                build_page_buttons(
                    code,
                    page,
                    total_page
                ),
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

        updated = False

        try:
            await call.message.edit_caption(
                caption=caption,
                reply_markup=keyboard
            )
            updated = True

        except TelegramBadRequest:
            pass

        if not updated:
            try:
                await call.message.edit_text(
                    text=caption,
                    reply_markup=keyboard
                )
                updated = True

            except TelegramBadRequest:
                pass

        await call.answer()
