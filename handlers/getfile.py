import json
import qrcode
import asyncio
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

router = Router()
PAGE_SIZE = 10


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

    return fid.strip() if len(fid.strip()) > 20 else None


# =========================
# TYPE NORMALIZER
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
# SEND FILE (AUTO UNLOCK)
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
# PAYMENT WATCHER (REALTIME)
# =========================
async def watch_payment(message, code, file, msg_id):
    for _ in range(60):  # 10 menit
        await asyncio.sleep(10)

        if await is_paid(message.from_user.id, code):
            try:
                await message.bot.delete_message(message.chat.id, msg_id)
            except:
                pass

            await message.answer("✅ PAYMENT SUCCESS")
            await send_file(message.bot, message.from_user.id, file)
            return


# =========================
# PAYMENT UI (QR FIXED)
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

    pay_url = invoice.get("checkout_url")
    reference = invoice.get("reference") or f"{message.from_user.id}_{file['code']}"

    await pool.execute(
        """
        INSERT INTO payments(user_id, code, reference, status)
        VALUES ($1,$2,$3,'pending')
        ON CONFLICT (user_id, code)
        DO UPDATE SET reference=EXCLUDED.reference, status='pending'
        """,
        message.from_user.id, file["code"], reference
    )

    # QR FIX AIogram v3
    qr = qrcode.make(pay_url)
    bio = BytesIO()
    qr.save(bio, format="PNG")
    bio.seek(0)

    photo = BufferedInputFile(bio.read(), filename="qris.png")

    price = int(file.get("price") or 0)

    msg = await message.answer_photo(
        photo=photo,
        caption=(
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n"
            "🔒 PAYMENT REQUIRED\n"
            "━━━━━━━━━━━━━━\n"
            f"🔑 CODE : {file['code']}\n"
            f"💰 PRICE : Rp{price:,}\n\n"
            "📌 SCAN QR UNTUK BAYAR"
        )
    )

    asyncio.create_task(
        watch_payment(message, file["code"], file, msg.message_id)
    )


# =========================
# GETFILE START
# =========================
@router.callback_query(F.data == "getfile")
async def getfile_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(GetFileState.wait_code)

    await call.message.answer(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n🔑 KIRIM KODE FILE"
    )

    await call.answer()


# =========================
# SEND MEDIA PAGE (FIXED NAV)
# =========================
async def send_media_page(message, file, media_list, page=1):

    total = max(1, (len(media_list) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total))

    chunk = media_list[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]

    group = []

    for i, m in enumerate(chunk):
        fid = clean_file_id(m.get("file_id"))
        if not fid:
            continue

        caption = None
        if i == 0:
            caption = (
                "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n"
                f"🔑 CODE : {file['code']}\n"
                f"📄 PAGE : {page}/{total}"
            )

        ftype = normalize_type(m.get("type"), fid)

        if ftype == "photo":
            group.append(InputMediaPhoto(media=fid, caption=caption))
        elif ftype == "video":
            group.append(InputMediaVideo(media=fid, caption=caption))
        else:
            group.append(InputMediaDocument(media=fid, caption=caption))

    if group:
        await message.answer_media_group(group)

    keyboard = [
        [InlineKeyboardButton("📂 GROUP", callback_data=f"group:{file['code']}")]
    ]

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ PREV", callback_data=f"page:{file['code']}:{page-1}"))
    if page < total:
        nav.append(InlineKeyboardButton("NEXT ➡️", callback_data=f"page:{file['code']}:{page+1}"))

    if nav:
        keyboard.append(nav)

    await message.answer(
        f"📄 Page {page}/{total}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


# =========================
# RECEIVE CODE (FIXED FREE + PAID)
# =========================
@router.message(GetFileState.wait_code)
async def receive_code(message: Message, state: FSMContext):

    if not message.text:
        return await message.answer("❌ Kirim kode file")

    code = message.text.strip().upper()

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code=$1",
        code
    )

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
    # FREE FILE FIX (NO DEAD BOT)
    # =========================
    if str(file.get("type")) == "free":
        await send_media_page(message, file, media, 1)
        await state.clear()
        return

    # =========================
    # PAID FILE
    # =========================
    if not await is_paid(message.from_user.id, code):
        await payment_ui(message, file)
        await state.clear()
        return

    await send_media_page(message, file, media, 1)
    await state.clear()
