import asyncio
import json
import httpx

from aiogram.types import (
    Message,
    CallbackQuery,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from utils.payment import create_invoice

from database import get_pool
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL

router = Router()
PAGE_SIZE = 10


# =========================
# CLEAN FILE ID (ULTRA FIX)
# =========================
def clean_file_id(fid):
    # unwrap dict berkali-kali
    while isinstance(fid, dict):
        fid = fid.get("file_id")

    # 🔥 kalau string JSON → decode lagi
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

    # 🔥 support semua prefix Telegram valid
    if not fid.startswith(("BA", "CA", "Ag", "BQ")):
        return None

    if len(fid) < 20:
        return None

    return fid


# =========================
# STATE
# =========================
class GetFileState(StatesGroup):
    wait_code = State()


# =========================
# NORMALIZE TYPE
# =========================
def normalize_type(ftype: str, file_id: str) -> str:

    if ftype:
        ftype = ftype.lower()

        if ftype in ["photo", "image", "jpg", "jpeg", "png"]:
            return "photo"

        if ftype in ["video", "mp4", "mov"]:
            return "video"

        if ftype in ["doc", "document", "file", "pdf", "zip"]:
            return "document"

    # fallback dari file_id
    if file_id.startswith("AgACAg"):
        return "photo"

    if file_id.startswith("BAACAg"):
        return "document"

    if file_id.startswith("BQACAg"):
        return "video"

    return "document"

# =========================
# START
# =========================
@router.callback_query(F.data == "getfile")
async def getfile_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(GetFileState.wait_code)

    await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n🔑 KIRIM KODE FILE SEKARANG"
    )


# =========================
# CHECK PAYMENT
# =========================
async def is_paid(user_id: int, code: str):
    pool = await get_pool()

    row = await pool.fetchrow(
        """
        SELECT 1 FROM payments
        WHERE user_id=$1 AND code=$2 AND status='paid'
        """,
        user_id,
        code
    )

    return bool(row)


# =========================
# PAYMENT UI (FULL MAX)
# =========================
async def payment_ui(message: Message, file):
    invoice = await create_invoice(
        amount=file["price"],
        code=file["code"],
        user_id=message.from_user.id
    )

    if invoice is None:
        await message.answer("❌ Gagal membuat invoice")
        return

    pay_url = invoice.get("checkout_url")
    reference = invoice.get("reference")

    if not pay_url:
        await message.answer("❌ Invoice invalid")
        return

    if not reference:
        reference = f"{message.from_user.id}_{file['code']}"

    pool = await get_pool()

    await pool.execute(
        """
        INSERT INTO payments (user_id, code, reference, status)
        VALUES ($1,$2,$3,'pending')
        ON CONFLICT DO NOTHING
        """,
        message.from_user.id,
        file["code"],
        reference
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 BAYAR",
                    url=pay_url
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 CEK PEMBAYARAN",
                    callback_data=f"cekpay:{file['code']}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ BATALKAN",
                    callback_data="cancel_payment"
                )
            ]
        ]
    )

    await message.answer(
        f"""𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

🔒 𝗙𝗜𝗟𝗘 𝗟𝗢𝗖𝗞𝗘𝗗
━━━━━━━━━━━━━━
🔑 𝗖𝗢𝗗𝗘   : {file['code']}
💰 𝗣𝗥𝗜𝗖𝗘 : Rp{file['price']:,}

⚡ 𝗦𝗲𝘁𝗲𝗹𝗮𝗵 𝗽𝗲𝗺𝗯𝗮𝘆𝗮𝗿𝗮𝗻 𝗳𝗶𝗹𝗲 𝗮𝗸𝗮𝗻 𝗼𝘁𝗼𝗺𝗮𝘁𝗶𝘀 𝘁𝗲𝗿𝗯𝘂𝗸𝗮.
""",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("page:"))
async def page_handler(call: CallbackQuery):

    _, code, page = call.data.split(":")

    page = int(page)

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code=$1",
        code
    )

    if not file:
        await call.answer(
            "❌ File tidak ditemukan",
            show_alert=True
        )
        return

    raw_media = file.get("media")

    if isinstance(raw_media, str):
        raw_media = json.loads(raw_media)

    await send_media_page(
        call.message,
        file,
        raw_media,
        page
    )

    await call.answer()

@router.callback_query(F.data.startswith("group:"))
async def group_handler(call: CallbackQuery):

    code = call.data.split(":")[1]

    await call.answer(
        f"📂 GROUP FILE\n\n🔑 {code}",
        show_alert=True
    )

# =========================
# CEK PEMBAYARAN
# =========================
@router.callback_query(F.data.startswith("cekpay:"))
async def cek_pembayaran(call: CallbackQuery):
    code = call.data.split(":")[1]

    paid = await is_paid(call.from_user.id, code)

    if paid:
        await call.answer(
            "✅ Pembayaran sudah diterima.\nSilakan kirim ulang kode file.",
            show_alert=True
        )
    else:
        await call.answer(
            "⌛ Pembayaran belum terdeteksi.",
            show_alert=True
        )

# =========================
# BATALKAN
# =========================
@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(call: CallbackQuery, state: FSMContext):
    await state.clear()

    await call.message.edit_text(
        "❌ Permintaan pembayaran dibatalkan."
    )

    await call.answer()

# =========================
# SEND MEDIA PAGE
# =========================
async def send_media_page(message, file, media_list, page=1):

    total_pages = (len(media_list) + PAGE_SIZE - 1) // PAGE_SIZE

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE

    chunk = media_list[start:end]

    group = []

    for i, m in enumerate(chunk):
        fid = clean_file_id(m.get("file_id"))

        if not fid:
            continue

        caption = None

        if i == 0:
            caption = (
                "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n"
                f"🔑 CODE  : {file['code']}\n"
                f"📄 PAGE  : {page}/{total_pages}\n"
                f"📦 TOTAL : {len(media_list)} MEDIA"
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

    keyboard = []

    keyboard.append([
        InlineKeyboardButton(
            text="📂 GROUP CODE",
            callback_data=f"group:{file['code']}"
        )
    ])

    nav = []

    if page > 1:
        nav.append(
            InlineKeyboardButton(
                text="🔙 PREV",
                callback_data=f"page:{file['code']}:{page-1}"
            )
        )

    if page < total_pages:
        nav.append(
            InlineKeyboardButton(
                text="🔜 NEXT",
                callback_data=f"page:{file['code']}:{page+1}"
            )
        )

    if nav:
        keyboard.append(nav)

    await message.answer(
        f"📄 Halaman {page}/{total_pages}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=keyboard
        )
    )
# =========================
# MAIN GETFILE
# =========================
@router.message(GetFileState.wait_code)
async def receive_code(message: Message, state: FSMContext):
    try:
        if not message.text:
            await message.answer("❌ Kirim kode saja")
            return

        code = message.text.strip().upper()
        print("GETFILE:", code)

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
        # PARSE MEDIA (ULTRA FIX)
        # =========================
        raw_media = file.get("media") or file.get("file_id")

        if isinstance(raw_media, str):
            try:
                raw_media = json.loads(raw_media)
            except:
                raw_media = []

        # 🔥 FIX STRING DALAM STRING
        if isinstance(raw_media, list) and len(raw_media) == 1:
            first = raw_media[0]
            if isinstance(first, dict) and isinstance(first.get("file_id"), str):
                try:
                    raw_media = json.loads(first["file_id"])
                except:
                    pass

        media_list = raw_media if isinstance(raw_media, list) else []

        if not media_list:
            await message.answer("❌ Media kosong")
            await state.clear()
            return

        caption = (
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n"
            f"🔑 CODE  : {file['code']}\n"
            f"📦 MEDIA : {len(media_list)}\n"
            f"👤 OWNER : {file['creator']}"
        )

        # =========================
        # BUILD GROUP
        # =========================
        group = []

        for i, m in enumerate(media_list[:10]):
            fid = clean_file_id(m.get("file_id"))

            if not fid:
                print("SKIP INVALID:", m)
                continue

            cap = caption if i == 0 else None
            ftype = normalize_type(m.get("type"), fid)

            try:
                if ftype == "photo":
                    group.append(InputMediaPhoto(media=fid, caption=cap))
                elif ftype == "video":
                    group.append(InputMediaVideo(media=fid, caption=cap))
                else:
                    group.append(InputMediaDocument(media=fid, caption=cap))
            except Exception as e:
                print("BUILD ERROR:", e)

        if not group:
            await message.answer("❌ Semua media rusak")
            await state.clear()
            return

        # =========================
        # SAFE SEND
        # =========================
        async def safe_send():
            try:
                await message.answer_media_group(group)
                return True
            except Exception as e:
                print("GROUP SEND FAIL:", e)

                for i, m in enumerate(media_list):
                    fid = clean_file_id(m.get("file_id"))
                    if not fid:
                        continue

                    cap = caption if i == 0 else None
                    ftype = normalize_type(m.get("type"), fid)

                    try:
                        if ftype == "photo":
                            await message.answer_photo(fid, caption=cap)
                        elif ftype == "video":
                            await message.answer_video(fid, caption=cap)
                        else:
                            await message.answer_document(fid, caption=cap)
                    except Exception as err:
                        print("TOTAL SEND FAIL:", err)

                return False

        # =========================
        # FREE
        # =========================
        if dict(file).get("type") == "free":
            await safe_send()
            await state.clear()
            return

        await send_media_page(
    message,
    file,
    media_list,
    1
)

        # =========================
        # PAYMENT
        # =========================
        paid = await is_paid(message.from_user.id, code)

        if not paid:
            await payment_ui(message, file)
            await state.clear()
            return

        await send_media_page(
    message,
    file,
    media_list,
    1
)

        # =========================
        # UNLOCKED
        # =========================
        if group:
            group[0].caption = f"{file['code']} • UNLOCKED"

        await safe_send()
        await state.clear()

    except Exception as e:
        print("FATAL GETFILE ERROR:", e)
        await message.answer("❌ Terjadi error")
        await state.clear()
