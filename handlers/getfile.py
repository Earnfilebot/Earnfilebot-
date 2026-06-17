import json
import asyncio

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
# GET FILE START
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

    media = json.loads(file["media"])
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
    # ACCESS CHECK
    # =========================
    if file_type == "paid":

        access = await pool.fetchrow(
            "SELECT 1 FROM user_access WHERE user_id=$1 AND code=$2 AND paid=true",
            user_id, code
        )

        if not access:

            pending = await pool.fetchrow(
                "SELECT 1 FROM payments WHERE user_id=$1 AND code=$2 AND status='pending'",
                user_id, code
            )

            if pending:
                await message.answer("⏳ INVOICE MASIH AKTIF")
                await state.clear()
                return

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"💰 BUY ACCESS ({price})",
                            callback_data=f"buy:{code}"
                        )
                    ]
                ]
            )

            await message.answer(
                "🔒 FILE BERBAYAR",
                reply_markup=keyboard
            )

            await state.clear()
            return

    # =========================
    # SHOW FILE
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
        f"💰 TYPE: {file_type.upper()}"
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
# BUY
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
        return await call.answer("NOT FOUND", show_alert=True)

    price = file["price"]

    exist = await pool.fetchrow(
        "SELECT 1 FROM payments WHERE user_id=$1 AND code=$2 AND status='pending'",
        user_id, code
    )

    if exist:
        return await call.answer("INVOICE MASIH AKTIF", show_alert=True)

    invoice_id = f"INV_{user_id}_{code}"

    await pool.execute(
        """
        INSERT INTO payments(user_id, code, amount, status, provider, invoice_id)
        VALUES ($1,$2,$3,'pending','qris',$4)
        """,
        user_id, code, price, invoice_id
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 BAYAR SEKARANG",
                    callback_data=f"pay:{invoice_id}"
                )
            ]
        ]
    )

    await call.message.edit_text(
        f"💰 INVOICE\nCODE: {code}\nTOTAL: {price}",
        reply_markup=keyboard
    )

    await call.answer()


# =========================
# PAYMENT SUCCESS
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

    await pool.execute(
        "UPDATE payments SET status='paid' WHERE invoice_id=$1",
        invoice_id
    )

    await pool.execute(
        """
        INSERT INTO user_access(user_id, code, paid)
        VALUES ($1,$2,true)
        ON CONFLICT (user_id, code)
        DO UPDATE SET paid=true
        """,
        user_id, code
    )

    await call.bot.send_message(
        user_id,
        f"✅ PAYMENT SUCCESS\nACCESS UNLOCKED: {code}"
    )

    await call.answer("PAID SUCCESS")
