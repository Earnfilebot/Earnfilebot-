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
    # COOLDOWN
    # =========================
    click_key = f"{user_id}:{code}:{page}"
    if now - CLICK_COOLDOWN[click_key] < 2:
        return await call.answer("⏳ Terlalu cepat", show_alert=True)

    CLICK_COOLDOWN[click_key] = now

    async with USER_LOCK[user_id]:
        pool = await get_pool()

        file = await pool.fetchrow(
            "SELECT * FROM files WHERE code=$1",
            code
        )

        if not file:
            return await call.answer("❌ File tidak ditemukan", show_alert=True)

        # =========================
        # PAID CHECK
        # =========================
        if file["is_paid"]:

            bought = False

            if user_id == file["owner_id"]:
                bought = True
            else:
                vip = await pool.fetchval(
                    """
                    SELECT 1
                    FROM users
                    WHERE telegram_id=$1
                      AND vip=TRUE
                      AND vip_until > NOW()
                    """,
                    user_id
                )

                if vip:
                    bought = True
                else:
                    bought = bool(await pool.fetchval(
                        """
                        SELECT 1
                        FROM file_purchases
                        WHERE user_id=$1
                          AND file_code=$2
                        LIMIT 1
                        """,
                        user_id,
                        code
                    ))

            if not bought:
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=f"💳 Bayar Rp {file['price']:,}".replace(",", "."),
                                callback_data=f"pay:{code}"
                            )
                        ]
                    ]
                )

                await call.message.answer(
                    (
                        "🔒 <b>FILE BERBAYAR</b>\n\n"
                        f"💰 Harga : Rp {file['price']:,}\n\n"
                        "Silakan beli file terlebih dahulu atau gunakan akses VIP."
                    ).replace(",", "."),
                    parse_mode="HTML",
                    reply_markup=kb
                )

                return await call.answer()

        # =========================
        # 24H LOCK PER PAGE
        # =========================
        page_key = f"{user_id}:{code}:{page}"
        last_open = USER_PAGE_LOCK.get(page_key)

        if last_open and now - last_open < 86400:
            return await call.answer(
                "⛔ Page ini sudah dibuka, tunggu 24 jam",
                show_alert=True
            )

        USER_PAGE_LOCK[page_key] = now

        # =========================
        # MEDIA PARSE
        # =========================
        media = file["media"]

        if isinstance(media, str):
            try:
                media = json.loads(media)
            except Exception:
                media = []

        if not media:
            return await call.answer("❌ File kosong", show_alert=True)

        total_page = max(1, (len(media) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(1, min(page, total_page))

        chunk = media[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]

        caption = (
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"🔑 CODE : {code}\n"
            f"📦 PAGE : {page}/{total_page}\n"
            f"📊 TOTAL : {len(media)} FILE"
        )

        # =========================
        # KEYBOARD
        # =========================
        if total_page <= 1:
            buttons = [
                [
                    InlineKeyboardButton(
                        text="📢 Channel Update",
                        url="https://t.me/+F6-XB1gFA9VhMDc1"
                    ),
                    InlineKeyboardButton(
                        text="🔔 Notifikasi Code",
                        url="https://t.me/+T8c4gdEWf843ZWQ1"
                    )
                ]
            ]
        else:
            buttons = [
                build_page_buttons(code, page, total_page),
                [
                    InlineKeyboardButton(
                        text="📢 Channel Update",
                        url="https://t.me/+F6-XB1gFA9VhMDc1"
                    ),
                    InlineKeyboardButton(
                        text="🔔 Notifikasi Code",
                        url="https://t.me/+T8c4gdEWf843ZWQ1"
                    )
                ]
            ]

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        # =========================
        # MEDIA GROUP
        # =========================
        album = []

        for i, item in enumerate(chunk):

            fid = clean_file_id(item.get("file_id"))
            ftype = normalize_type(item.get("type"))

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
            return await call.answer("❌ Tidak ada media", show_alert=True)

        await call.message.answer_media_group(media=album)

        await call.message.answer("📦 NAVIGATION", reply_markup=keyboard)

        await call.answer()
