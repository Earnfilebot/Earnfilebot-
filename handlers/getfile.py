import json
import asyncio
import qrcode
from io import BytesIO

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.payment import create_invoice
from database import get_pool

PAGE_CACHE = {}
CLICK_LOCK = {}
router = Router()
PAGE_SIZE = 10

def get_cache(code, page):
    return PAGE_CACHE.get(f"{code}:{page}")


def set_cache(code, page, data):
    PAGE_CACHE[f"{code}:{page}"] = data


def is_locked(user_id):
    return CLICK_LOCK.get(user_id, False)


def lock(user_id):
    CLICK_LOCK[user_id] = True


def unlock(user_id):
    CLICK_LOCK[user_id] = False
# =========================
# UI FONT
# =========================
UI_TITLE = "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫"
UI_LINE = "━━━━━━━━━━━━━━"


# =========================
# STATE
# =========================
class GetFileState(StatesGroup):
    wait_code = State()


# =========================
# CLEAN FILE ID
# =========================

    
def clean_file_id(fid):
    while isinstance(fid, dict):
        fid = fid.get("file_id")

    if isinstance(fid, str) and fid.startswith("["):
        try:
            data = json.loads(fid)
            if isinstance(data, list) and data:
                return clean_file_id(data[0].get("file_id"))
        except:
            return None

    if not isinstance(fid, str):
        return None

    fid = fid.strip()
    return fid if len(fid) > 20 else None


# =========================
# TYPE
# =========================
def normalize_type(ftype, file_id):
    if ftype:
        ftype = ftype.lower()
        if ftype in ("photo", "jpg", "png", "image"):
            return "photo"
        if ftype in ("video", "mp4", "mov"):
            return "video"

    if isinstance(file_id, str):
        if file_id.startswith("AgACAg"):
            return "photo"
        if file_id.startswith("BQACAg"):
            return "video"

    return "document"


# =========================
# PAYMENT CHECK
# =========================
async def is_paid(user_id, code):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT status FROM payments WHERE user_id=$1 AND code=$2 AND status='paid'",
        user_id, code
    )
    return bool(row)


# =========================
# SEND FILE
# =========================
async def send_file(bot, user_id, file):
    media = file.get("media") or []

    if isinstance(media, str):
        try:
            media = json.loads(media)
        except:
            media = []

    if not isinstance(media, list):
        return

    for m in media[:10]:
        fid = m.get("file_id")
        if fid:
            try:
                await bot.send_document(user_id, fid)
            except:
                pass


# =========================
# PAYMENT UI (ONLY 1 VERSION FIXED)
# =========================
async def payment_ui(message: Message, file):
    pool = await get_pool()

    invoice = await create_invoice(
        amount=file["price"],
        code=file["code"],
        user_id=message.from_user.id
    )

    if not invoice:
        return await message.answer("❌ Invoice error")

    # =========================
    # QRIS SAFE PARSER (ANTI ERROR STRUCTURE)
    # =========================
    qr_data = None

    if isinstance(invoice, dict):
        qr_data = (
            invoice.get("qris_string")
            or (invoice.get("data") or {}).get("qris_string")
            or invoice.get("data", {}).get("qris_string")
        )

    if not qr_data:
        return await message.answer("❌ QRIS tidak tersedia")

    reference = invoice.get("reference") or f"{message.from_user.id}_{file['code']}"

    # =========================
    # 🔴 ANTI DUPLICATE PAYMENT (RACE CONDITION SAFE)
    # =========================
    await pool.execute("""
        INSERT INTO payments(user_id, code, reference, status)
        VALUES ($1,$2,$3,'pending')
        ON CONFLICT (user_id, code)
        DO UPDATE SET reference=EXCLUDED.reference, status='pending'
    """, message.from_user.id, file["code"], reference)

    # =========================
    # QR GENERATOR
    # =========================
    qr = qrcode.make(qr_data)

    bio = BytesIO()
    bio.name = "qris.png"
    qr.save(bio)
    bio.seek(0)

    photo = BufferedInputFile(bio.getvalue(), filename="qris.png")

    price = int(file.get("price") or 0)

    # =========================
    # CLEAN UI FONT (RAPI + CONSISTENT)
    # =========================
    caption = (
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫 𝗣𝗔𝗬𝗠𝗘𝗡𝗧\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🔐 𝗜𝗡𝗩𝗢𝗜𝗖𝗘 𝗗𝗘𝗧𝗔𝗜𝗟𝗦\n"
        "──────────────────\n\n"
        f"▸ 𝗖𝗢𝗗𝗘   : {file['code']}\n"
        f"▸ 𝗣𝗥𝗜𝗖𝗘  : Rp{price:,}\n"
        f"▸ 𝗦𝗧𝗔𝗧𝗨𝗦 : PENDING\n\n"
        "⚡ Scan QR untuk melakukan pembayaran\n"
        "🔄 Auto unlock setelah pembayaran sukses"
    )

    await message.answer_photo(
        photo=photo,
        caption=caption
    )
# =========================
# GETFILE START
# =========================
@router.callback_query(F.data == "getfile")
async def getfile_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(GetFileState.wait_code)
    await call.message.answer(f"{UI_TITLE}\n\n🔑 KIRIM KODE FILE")
    await call.answer()


# =========================
# SEND MEDIA PAGE
# =========================
@router.callback_query(F.data.startswith("page:"))
async def page_handler(call: CallbackQuery):
    user_id = call.from_user.id

    if is_locked(user_id):
        return await call.answer("⏳ Tunggu...", show_alert=False)

    lock(user_id)

    try:
        _, code, page = call.data.split(":")
        page = int(page)

        pool = await get_pool()

        file = await pool.fetchrow(
            "SELECT * FROM files WHERE code=$1",
            code
        )

        if not file:
            return await call.answer("❌ FILE NOT FOUND", show_alert=True)

        media = file.get("media") or []
        if isinstance(media, str):
            media = json.loads(media)

        if not isinstance(media, list):
            media = []

        total = max(1, (len(media) + PAGE_SIZE - 1) // PAGE_SIZE)

        # 🔥 CLAMP PAGE (WAJIB)
        page = max(1, min(page, total))

        chunk = media[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]

        if not chunk:
            return await call.answer("❌ EMPTY PAGE", show_alert=True)

        first = chunk[0]
        fid = clean_file_id(first.get("file_id"))
        ftype = normalize_type(first.get("type"), fid)

        caption = (
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫 𝗙𝗜𝗟𝗘\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"▸ 𝗖𝗢𝗗𝗘 : {code}\n"
            f"▸ 𝗣𝗔𝗚𝗘 : {page}/{total}\n"
            f"▸ 𝗧𝗢𝗧𝗔𝗟 : {len(media)} FILE\n"
        )

        # media builder
        if ftype == "photo":
            media_obj = InputMediaPhoto(media=fid, caption=caption)
        elif ftype == "video":
            media_obj = InputMediaVideo(media=fid, caption=caption)
        else:
            media_obj = InputMediaDocument(media=fid, caption=caption)

        # =========================
        # BUTTONS FIX (NO PAGE 0 BUG)
        # =========================
        nav = []

        if page > 1:
            nav.append(
                InlineKeyboardButton(
                    "⬅️ PREV",
                    callback_data=f"page:{code}:{page-1}"
                )
            )

        if page < total:
            nav.append(
                InlineKeyboardButton(
                    "NEXT ➡️",
                    callback_data=f"page:{code}:{page+1}"
                )
            )

        buttons = []

        if nav:
            buttons.append(nav)

        buttons.append([
            InlineKeyboardButton("📂 GROUP", callback_data=f"group:{code}")
        ])

        buttons.append([
            InlineKeyboardButton(
                "🔔 JOIN NOTIFIKASI",
                url="https://t.me/+DTL9cOR34ipmM2U1"
            )
        ])

        # =========================
        # SMOOTH EDIT (NO CRASH)
        # =========================
        try:
            await call.message.edit_media(media=media_obj)
        except:
            pass

        try:
            await call.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
        except:
            pass

        await call.answer()

    finally:
        unlock(user_id)
# =========================
# RECEIVE CODE (FIXED FLOW)
# =========================
@router.message(GetFileState.wait_code)
async def receive_code(message: Message, state: FSMContext):

    if not message.text:
        return await message.answer("❌ Kirim kode file")

    code = message.text.strip().upper()

    pool = await get_pool()

    file = await pool.fetchrow("SELECT * FROM files WHERE code=$1", code)

    if not file:
        await message.answer("❌ CODE TIDAK DITEMUKAN")
        await state.clear()
        return

    media = file.get("media") or []

    if isinstance(media, str):
        try:
            media = json.loads(media)
        except:
            media = []

    if not isinstance(media, list):
        media = []

    # =========================
    # ACCESS CHECK
    # =========================
    is_free = str(file.get("type")) == "free"
    paid = await is_paid(message.from_user.id, code)

    if not is_free and not paid:
        await payment_ui(message, file)
        await state.clear()
        return

    # =========================
    # PAGE INIT
    # =========================
    page = 1
    total = max(1, (len(media) + PAGE_SIZE - 1) // PAGE_SIZE)

    chunk = media[:PAGE_SIZE]

    if not chunk:
        return await message.answer("❌ FILE KOSONG")

    first = chunk[0]
    fid = clean_file_id(first.get("file_id"))
    ftype = normalize_type(first.get("type"), fid)

    caption = (
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫 𝗙𝗜𝗟𝗘\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"▸ 𝗖𝗢𝗗𝗘 : {code}\n"
        f"▸ 𝗣𝗔𝗚𝗘 : {page}/{total}\n"
        f"▸ 𝗧𝗢𝗧𝗔𝗟 : {len(media)} FILE\n"
    )

    # =========================
    # CACHE PAGE 1
    # =========================
    set_cache(code, page, (
        file, media, total, chunk, fid, caption, ftype
    ))

    # =========================
    # BUTTONS (FIXED NAV)
    # =========================
    buttons = [
        [
            InlineKeyboardButton(
                "⬅️ PREV", callback_data=f"page:{code}:{page-1}"
            ),
            InlineKeyboardButton(
                "NEXT ➡️", callback_data=f"page:{code}:{page+1}"
            )
        ],
        [
            InlineKeyboardButton("📂 GROUP", callback_data=f"group:{code}")
        ],
        [
            InlineKeyboardButton(
                "🔔 JOIN NOTIFIKASI",
                url="https://t.me/+DTL9cOR34ipmM2U1"
            )
        ]
    ]

    # =========================
    # BUILD MEDIA (FIRST PAGE)
    # =========================
    if ftype == "photo":
        media_obj = InputMediaPhoto(media=fid, caption=caption)
    elif ftype == "video":
        media_obj = InputMediaVideo(media=fid, caption=caption)
    else:
        media_obj = InputMediaDocument(media=fid, caption=caption)

    # =========================
    # SEND FIRST MESSAGE
    # =========================
    await message.answer_photo(
        photo=fid,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

    await state.clear()
