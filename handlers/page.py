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

SAME_PAGE_COOLDOWN = 3600      # 1 jam
CHANGE_PAGE_COOLDOWN = 30      # 30 detik

USER_LOCK = defaultdict(lambda: asyncio.Lock())

PAGE_CACHE = {}
PAGE_CHANGE = {}
NAV_CACHE = {}

# =========================
# UTIL
# =========================
async def clear_cache_loop():

    while True:

        await asyncio.sleep(3600)

        now = time.time()

        for cache in [PAGE_CACHE, PAGE_CHANGE, NAV_CACHE]:

            remove = []

            for key, value in list(cache.items()):

                if now - value[1] > 7200:
                    remove.append(key)


            for key in remove:
                del cache[key]
                
def clean_file_id(fid):
    return fid.get("file_id") if isinstance(fid, dict) else fid


def normalize_type(ftype):
    return (ftype or "document").lower()


# =========================
# SEND PAGE (REUSABLE CORE)
# =========================
async def send_page(bot, chat_id, user_id, code, page=1):

    pool = await get_pool()

    file = await pool.fetchrow(
        """
        SELECT *
        FROM files
        WHERE code=$1
        """,
        code
    )

    if not file:
        print("FILE NOT FOUND")
        return False


    # =========================
    # ACCESS CHECK
    # =========================

    bought = False

    if not file["is_paid"]:
        bought = True

    elif user_id == file["owner_id"]:
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

            bought = bool(
                await pool.fetchval(
                    """
                    SELECT 1
                    FROM file_purchases
                    WHERE user_id=$1
                    AND file_code=$2
                    AND status='paid'
                    LIMIT 1
                    """,
                    user_id,
                    code
                )
            )


    if not bought:
        print(
            "ACCESS DENIED",
            user_id,
            code
        )
        return False



    # =========================
    # LOAD MEDIA
    # =========================

    media = file["media"]

    if isinstance(media, str):
        try:
            media = json.loads(media)
        except Exception:
            print("MEDIA JSON ERROR")
            return False

    if not isinstance(media, list) or not media:
        print("MEDIA EMPTY")
        return False

    total_page = max(
        1,
        (len(media) + PAGE_SIZE - 1) // PAGE_SIZE
    )

    page = max(
        1,
        min(page, total_page)
    )

    # =========================
    # DOWNLOAD COUNTER
    # =========================
    if page == 1:
        await pool.execute(
            """
            UPDATE files
            SET download_count = download_count + 1
            WHERE code=$1
            """,
            code
        )

    chunk = media[
        (page - 1) * PAGE_SIZE:
        page * PAGE_SIZE
    ]

    caption = (
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"🔑 CODE : {code}\n"
        f"📦 PAGE : {page}/{total_page}\n"
        f"📊 TOTAL : {len(media)} FILE"
    )

    protect = not file["share_media"]


    album = []



    for index, item in enumerate(chunk):

        if not isinstance(item, dict):
            continue


        fid = item.get("file_id")

        ftype = (
            item.get("type")
            or "document"
        ).lower()


        if not fid:
            continue


        cap = caption if index == 0 else None


        if ftype in ("photo", "image"):

            album.append(
                InputMediaPhoto(
                    media=fid,
                    caption=cap
                )
            )


        elif ftype == "video":

            album.append(
                InputMediaVideo(
                    media=fid,
                    caption=cap
                )
            )


        else:

            album.append(
                InputMediaDocument(
                    media=fid,
                    caption=cap
                )
            )



    if not album:
        print("ALBUM EMPTY")
        return False



    try:

        # =========================
        # SEND MEDIA
        # =========================

        if len(album) == 1:

            item = chunk[0]

            fid = item.get("file_id")
            ftype = (
                item.get("type")
                or "document"
            ).lower()


            if ftype in ("photo","image"):

                await bot.send_photo(
                    chat_id,
                    fid,
                    caption=caption,
                    protect_content=protect
                )


            elif ftype == "video":

                await bot.send_video(
                    chat_id,
                    fid,
                    caption=caption,
                    protect_content=protect
                )


            else:

                await bot.send_document(
                    chat_id,
                    fid,
                    caption=caption,
                    protect_content=protect
                )


        else:

            await bot.send_media_group(
                chat_id,
                album,
                protect_content=protect
            )



        # =========================
        # BUTTON
        # =========================

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
                        url="https://t.me/+T8c4gdEWf843ZWQ1"
                    )

                ]

            ]
        )


        nav_msg = await bot.send_message(
            chat_id,
            "📦 NAVIGATION",
            reply_markup=keyboard
        )

        NAV_CACHE[(user_id, code)] = nav_msg.message_id


        print(
            "SEND PAGE SUCCESS",
            code,
            page
        )


        return True



    except Exception as e:

        print(
            "SEND MEDIA ERROR",
            repr(e)
        )

        return False


# =========================
# BUTTON
# =========================
def build_page_buttons(code: str, page: int, total: int):

    row = []


    # PREV
    if page > 1:
        row.append(
            InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=f"page:{code}:{page-1}"
            )
        )


    # NOMOR HALAMAN
    start = max(1, page - 2)
    end = min(total, page + 2)

    for i in range(start, end + 1):

        emoji = "🟡" if i == page else (
            "🟢" if i < page else "🔴"
        )

        row.append(
            InlineKeyboardButton(
                text=f"{i}{emoji}",
                callback_data=f"page:{code}:{i}"
            )
        )


    # NEXT
    if page < total:

        row.append(
            InlineKeyboardButton(
                text="Next ➡️",
                callback_data=f"page:{code}:{page+1}"
            )
        )

    else:

        row.append(
            InlineKeyboardButton(
                text="✅ END",
                callback_data="end_page"
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

    except:
        return await call.answer(
            "❌ Invalid data",
            show_alert=True
        )


    now = time.time()

    key = (user_id, code)


    # =========================
    # SAME PAGE COOLDOWN
    # =========================
    last = PAGE_CACHE.get(key)

    if last:

        last_page, last_time = last

        if last_page == page:

            sisa = SAME_PAGE_COOLDOWN - (now - last_time)

            if sisa > 0:

                return await call.answer(
                    f"⏳ Halaman ini sudah dibuka.\n"
                    f"Coba lagi {int(sisa)} detik.",
                    show_alert=True
                )


    # =========================
    # CHANGE PAGE COOLDOWN
    # =========================
    change = PAGE_CHANGE.get(key)

    if change:

        old_page, old_time = change

        if old_page != page:

            sisa = CHANGE_PAGE_COOLDOWN - (now - old_time)

            if sisa > 0:

                return await call.answer(
                    f"⏳ Tunggu {int(sisa)} detik sebelum pindah halaman.",
                    show_alert=True
                )


    PAGE_CACHE[key] = (page, now)
    PAGE_CHANGE[key] = (page, now)



    async with USER_LOCK[user_id]:

        pool = await get_pool()


        file = await pool.fetchrow(
            """
            SELECT *
            FROM files
            WHERE code=$1
            """,
            code
        )


        if not file:

            return await call.answer(
                "❌ File tidak ditemukan",
                show_alert=True
            )



        # =========================
        # CEK BATAS HALAMAN
        # =========================

        media = file["media"]

        if isinstance(media, str):

            media = json.loads(media)


        total_page = max(
            1,
            (len(media) + PAGE_SIZE - 1) // PAGE_SIZE
        )


        if page > total_page:

            return await call.answer(
                "📄 Halaman sudah habis.",
                show_alert=True
            )



        # =========================
        # ACCESS CHECK
        # =========================

        bought = False


        if not file["is_paid"]:

            bought = True


        elif user_id == file["owner_id"]:

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

                bought = bool(
                    await pool.fetchval(
                        """
                        SELECT 1
                        FROM file_purchases
                        WHERE user_id=$1
                        AND file_code=$2
                        AND status='paid'
                        LIMIT 1
                        """,
                        user_id,
                        code
                    )
                )



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
                "🔒 <b>FILE BERBAYAR</b>\n\n"
                f"💰 Harga : Rp {file['price']:,}\n\n"
                "Silakan beli file atau gunakan VIP.",
                parse_mode="HTML",
                reply_markup=kb
            )


            return await call.answer()

        old_nav = NAV_CACHE.get((user_id, code))

        if old_nav:
            try:
                await call.bot.delete_message(
                    call.message.chat.id,
                    old_nav
                )
            except:
                pass
            NAV_CACHE.pop((user_id, code), None)

        await send_page(
            call.bot,
            call.message.chat.id,
            user_id,
            code,
            page
        )


        await call.answer()

@router.callback_query(F.data == "end_page")
async def end_page(call: CallbackQuery):

    await call.answer(
        "📄 Semua file sudah ditampilkan.",
        show_alert=True
    )
