import json
import asyncio
import qrcode
from io import BytesIO
from collections import defaultdict

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

CLICK_COOLDOWN = defaultdict(float)
USER_LOCK = defaultdict(lambda: asyncio.Lock())

COOLDOWN_SEC = 0.8

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
# RECEIVE CODE (FIXED FLOW)
# =========================
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_pool

router = Router()

# =========================
# STATE IMPORT (kalau kamu pakai FSM)
# =========================
from states import GetFileState  # sesuaikan kalau beda


# =========================
# UTIL
# =========================
def safe_json(data):
    if isinstance(data, str):
        try:
            return json.loads(data)
        except:
            return []
    return data or []


def get_first_media(media):
    if not media:
        return None
    return media[0]


# =========================
# ENTRY GET FILE
# =========================
@router.message(GetFileState.wait_code)
async def receive_code(message: Message, state):

    code = message.text.strip().upper()
    user_id = message.from_user.id

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code=$1",
        code
    )

    if not file:
        await message.answer("❌ CODE TIDAK DITEMUKAN")
        await state.clear()
        return

    # =========================
    # PARSE DATA
    # =========================
    media = safe_json(file.get("media"))
    file_type = file.get("type", "free")
    price = file.get("price", 0)

    if not media:
        await message.answer("❌ FILE KOSONG")
        await state.clear()
        return

    first = get_first_media(media)
    fid = first.get("file_id")
    ftype = (first.get("type") or "document").lower()

    if not fid:
        await message.answer("❌ FILE INVALID")
        await state.clear()
        return

    # =========================
    # ACCESS CHECK (PAID SYSTEM)
    # =========================
    if file_type == "paid":
        access = await pool.fetchrow(
            """
            SELECT 1 FROM user_access
            WHERE user_id=$1 AND code=$2 AND paid=true
            """,
            user_id, code
        )

        if not access:

            # cek invoice aktif
            pending = await pool.fetchrow(
                """
                SELECT * FROM payments
                WHERE user_id=$1 AND code=$2 AND status='pending'
                """,
                user_id, code
            )

            if pending:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⏳ MENUNGGU PEMBAYARAN",
                            callback_data="noop"
                        )
                    ]
                ])
                await message.answer(
                    "⏳ INVOICE MASIH AKTIF\nSelesaikan pembayaran terlebih dahulu."
                )
                await state.clear()
                return

            # tombol BUY
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"💰 BUY ACCESS ({price})",
                        callback_data=f"buy:{code}"
                    )
                ]
            ])

            await message.answer(
                "🔒 FILE BERBAYAR\n\nKlik untuk membeli akses.",
                reply_markup=keyboard
            )

            await state.clear()
            return

    # =========================
    # PAGE ENTRY BUTTON
    # =========================
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📂 OPEN FILE",
                callback_data=f"page:{code}:1"
            )
        ]
    ])

    caption = (
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 CODE : {code}\n"
        f"📊 TOTAL : {len(media)} FILE\n"
        f"💰 TYPE : {file_type.upper()}"
    )

    try:
        if ftype == "photo":
            await message.answer_photo(fid, caption=caption, reply_markup=keyboard)

        elif ftype == "video":
            await message.answer_video(fid, caption=caption, reply_markup=keyboard)

        else:
            await message.answer_document(fid, caption=caption, reply_markup=keyboard)

    except Exception as e:
        await message.answer(f"❌ ERROR: {e}")

    await state.clear()


# =========================
# BUY HANDLER (INLINE)
# =========================
@router.callback_query(F.data.startswith("buy:"))
async def buy_access(call: CallbackQuery):

    code = call.data.split(":")[1]
    user_id = call.from_user.id

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code=$1",
        code
    )

    if not file:
        return await call.answer("FILE NOT FOUND", show_alert=True)

    price = file["price"]

    # anti double invoice
    exist = await pool.fetchrow(
        """
        SELECT 1 FROM payments
        WHERE user_id=$1 AND code=$2 AND status='pending'
        """,
        user_id, code
    )

    if exist:
        return await call.answer("⚠️ INVOICE MASIH AKTIF", show_alert=True)

    invoice_id = f"INV_{user_id}_{code}"

    await pool.execute(
        """
        INSERT INTO payments (user_id, code, amount, status, provider, invoice_id)
        VALUES ($1,$2,$3,'pending','qris',$4)
        """,
        user_id, code, price, invoice_id
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💳 BAYAR SEKARANG",
                callback_data=f"pay:{invoice_id}"
            )
        ]
    ])

    await call.message.edit_text(
        f"💰 INVOICE\n\nCODE: {code}\nTOTAL: {price}",
        reply_markup=keyboard
    )

    await call.answer()


# =========================
# PAYMENT SUCCESS SIMULATION
# =========================
@router.callback_query(F.data.startswith("pay:"))
async def pay_handler(call: CallbackQuery):

    invoice_id = call.data.split(":")[1]
    pool = await get_pool()

    payment = await pool.fetchrow(
        "SELECT * FROM payments WHERE invoice_id=$1",
        invoice_id
    )

    if not payment:
        return await call.answer("INVALID INVOICE", show_alert=True)

    user_id = payment["user_id"]
    code = payment["code"]

    # update payment
    await pool.execute(
        "UPDATE payments SET status='paid' WHERE invoice_id=$1",
        invoice_id
    )

    # unlock access
    await pool.execute(
        """
        INSERT INTO user_access (user_id, code, paid)
        VALUES ($1,$2,true)
        ON CONFLICT (user_id, code)
        DO UPDATE SET paid=true
        """,
        user_id, code
    )

    await call.bot.send_message(
        user_id,
        f"✅ PAYMENT SUCCESS\n\nACCESS UNLOCKED: {code}"
    )

    await call.answer("PAID SUCCESS")
