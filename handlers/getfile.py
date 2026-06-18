import json
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_pool

router = Router()


# =========================
# STATE
# =========================
class GetFileState(StatesGroup):
    wait_code = State()


# =========================
# UTIL SAFE JSON
# =========================
def safe_json(data):
    if isinstance(data, str):
        try:
            return json.loads(data)
        except:
            return []
    return data or []


def get_first_media(media):
    if isinstance(media, list) and len(media) > 0:
        return media[0]
    return None


# =========================
# START
# =========================
@router.callback_query(F.data == "getfile")
async def getfile_start(call: CallbackQuery, state: FSMContext):

    await state.set_state(GetFileState.wait_code)

    await call.message.edit_text(
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n\n🔑 KIRIM KODE FILE"
    )

    await call.answer()


# =========================
# RECEIVE CODE
# =========================
@router.message(GetFileState.wait_code)
async def receive_code(message: Message, state: FSMContext):

    if not message.text:
        return await message.answer("❌ Kode kosong")

    code = message.text.strip().upper()
    user_id = message.from_user.id

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code=$1",
        code
    )

    # =========================
    # FILE NOT FOUND
    # =========================
    if not file:
        await message.answer("❌ CODE TIDAK DITEMUKAN")
        await state.clear()
        return

    # =========================
    # NORMALIZE DATA
    # =========================
    media = safe_json(file.get("media"))
    price = int(file.get("price") or 0)
    file_type = str(file.get("type") or "document")

    # =========================
    # EMPTY MEDIA CHECK
    # =========================
    if not isinstance(media, list) or len(media) == 0:
        await message.answer("❌ FILE KOSONG")
        await state.clear()
        return

    first = get_first_media(media)

    if not first or not first.get("file_id"):
        await message.answer("❌ FILE INVALID")
        await state.clear()
        return

    fid = first["file_id"]
    ftype = (first.get("type") or "document").lower()

    # =========================
    # FREE FILE LOGIC FIX
    # =========================
    is_free = price <= 0

    if is_free:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📂 OPEN FILE",
                        callback_data=f"page:{code}:1"
                    )
                ]
            ]
        )

        caption = (
            "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
            f"🔑 CODE: {code}\n"
            f"📊 FILE: {len(media)}\n"
            "🆓 TYPE: FREE"
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
        return

    # =========================
    # PAID FILE LOGIC
    # =========================
    access = await pool.fetchval(
        """
        SELECT 1 FROM user_access
        WHERE user_id=$1 AND code=$2 AND paid=true
        """,
        user_id, code
    )

    if not access:

        pending = await pool.fetchval(
            """
            SELECT 1 FROM payments
            WHERE user_id=$1 AND code=$2 AND status='pending'
            """,
            user_id, code
        )

        if pending:
            await message.answer("⏳ INVOICE MASIH AKTIF / BELUM LUNAS")
        else:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"💰 BUY ACCESS (Rp {price})",
                            callback_data=f"buy:{code}"
                        )
                    ]
                ]
            )

            await message.answer("🔒 FILE BERBAYAR", reply_markup=keyboard)

        await state.clear()
        return

    # =========================
    # PAID ACCESS GRANTED
    # =========================
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📂 OPEN FILE",
                    callback_data=f"page:{code}:1"
                )
            ]
        ]
    )

    caption = (
        "𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗫\n"
        f"🔑 CODE: {code}\n"
        f"📊 FILE: {len(media)}\n"
        f"💰 TYPE: PAID"
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
