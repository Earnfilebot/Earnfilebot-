import json
from aiogram import Router, F

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

router = Router()
PAGE_SIZE = 10
# =========================
# CLEAN FILE ID (ULTRA FIX)
# =========================
def clean_file_id(fid):
    # unwrap dict berkali-kali
    while isinstance(fid, dict):
        fid = fid.get("file_id")

    # kalau string JSON → decode lagi
    if isinstance(fid, str) and fid.startswith("["):
        try:
            data = json.loads(fid)

            if isinstance(data, list) and data:
                return clean_file_id(
                    data[0].get("file_id")
                )
        except Exception:
            return None

    # bukan string
    if not isinstance(fid, str):
        return None

    fid = fid.strip()

    # file_id kosong
    if not fid:
        return None

    # terlalu pendek kemungkinan invalid
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

        if ftype in (
            "photo", "image", "jpg",
            "jpeg", "png"
        ):
            return "photo"

        if ftype in (
            "video", "mp4", "mov"
        ):
            return "video"

        if ftype in (
            "doc", "document",
            "file", "pdf", "zip"
        ):
            return "document"

    # fallback dari file_id
    if isinstance(file_id, str):

        if file_id.startswith("AgACAg"):
            return "photo"

        if file_id.startswith("BQACAg"):
            return "video"

        if file_id.startswith("BAACAg"):
            return "document"

    return "document"
# =========================
# START GETFILE
# =========================
@router.callback_query(F.data == "getfile")
async def getfile_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(GetFileState.wait_code)

    try:
        await call.message.edit_text(
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n"
            "🔑 KIRIM KODE FILE SEKARANG"
        )
    except:
        await call.message.answer(
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n"
            "🔑 KIRIM KODE FILE SEKARANG"
        )

    await call.answer()
# =========================
# CHECK PAYMENT
# =========================
async def is_paid(user_id: int, code: str) -> bool:
    try:
        pool = await get_pool()

        row = await pool.fetchrow(
            """
            SELECT 1
            FROM payments
            WHERE user_id = $1
              AND code = $2
              AND status = 'paid'
            LIMIT 1
            """,
            user_id,
            code
        )

        return row is not None

    except Exception as e:
        print("IS_PAID ERROR:", e)
        return False

# =========================
# PAYMENT UI
# =========================
async def payment_ui(message: Message, file):
    try:
        invoice = await create_invoice(
            amount=file["price"],
            code=file["code"],
            user_id=message.from_user.id
        )

        if not invoice:
            await message.answer(
                "❌ Gagal membuat invoice."
            )
            return

        pay_url = invoice.get("checkout_url")
        reference = invoice.get("reference")

        if not pay_url:
            await message.answer(
                "❌ Invoice tidak valid."
            )
            return

        if not reference:
            reference = (
                f"{message.from_user.id}_{file['code']}"
            )

        pool = await get_pool()

        # Simpan / update pembayaran pending
        await pool.execute(
            """
            INSERT INTO payments (
                user_id,
                code,
                reference,
                status
            )
            VALUES ($1, $2, $3, 'pending')

            ON CONFLICT (user_id, code)
            DO UPDATE SET
                reference = EXCLUDED.reference
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

        price = int(file.get("price", 0))

        await message.answer(
            f"""𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫

🔒 𝗙𝗜𝗟𝗘 𝗟𝗢𝗖𝗞𝗘𝗗
━━━━━━━━━━━━━━
🔑 𝗖𝗢𝗗𝗘   : {file['code']}
💰 𝗣𝗥𝗜𝗖𝗘 : Rp{price:,}

⚡ Setelah pembayaran berhasil,
file akan otomatis terbuka.

📌 Tekan tombol BAYAR untuk melanjutkan.
""",
            reply_markup=keyboard
        )

    except Exception as e:
        print("PAYMENT_UI ERROR:", e)

        await message.answer(
            "❌ Terjadi kesalahan saat membuat pembayaran."
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

    # =========================
    # CEK AKSES PREMIUM
    # =========================
    if dict(file).get("type") != "free":

        paid = await is_paid(
            call.from_user.id,
            code
        )

        if not paid:
            await call.answer(
                "❌ File belum dibeli",
                show_alert=True
            )
            return

    # =========================
    # PARSE MEDIA
    # =========================
    raw_media = file.get("media") or file.get("file_id")

    if isinstance(raw_media, str):
        try:
            raw_media = json.loads(raw_media)
        except:
            raw_media = []

    try:
    await call.message.delete()
except:
    pass

    # =========================
    # KIRIM HALAMAN
    # =========================
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

if total_pages <= 0:
    total_pages = 1

if page < 1:
    page = 1

if page > total_pages:
    page = total_pages

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

    if not group:
    await message.answer(
        "❌ Semua media tidak valid"
    )
    return

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
        # PARSE MEDIA
        # =========================
        raw_media = file.get("media") or file.get("file_id")

        if isinstance(raw_media, str):
            try:
                raw_media = json.loads(raw_media)
            except:
                raw_media = []

        # FIX JSON DALAM JSON
        if isinstance(raw_media, list) and len(raw_media) == 1:
            first = raw_media[0]

            if (
                isinstance(first, dict)
                and isinstance(first.get("file_id"), str)
            ):
                try:
                    raw_media = json.loads(first["file_id"])
                except:
                    pass

        media_list = (
            raw_media
            if isinstance(raw_media, list)
            else []
        )

        if not media_list:
            await message.answer("❌ Media kosong")
            await state.clear()
            return

        # =========================
        # FREE FILE
        # =========================
        if dict(file).get("type") == "free":

            await send_media_page(
                message,
                file,
                media_list,
                1
            )

            await state.clear()
            return

        # =========================
        # PREMIUM / PAID FILE
        # =========================
        paid = await is_paid(
            message.from_user.id,
            code
        )

        if not paid:

            await payment_ui(
                message,
                file
            )

            await state.clear()
            return

        # =========================
        # UNLOCKED
        # =========================
        await send_media_page(
            message,
            file,
            media_list,
            1
        )

        await state.clear()

    except Exception as e:
        print("FATAL GETFILE ERROR:", e)

        await message.answer(
            "❌ Terjadi error"
        )

        await state.clear()
