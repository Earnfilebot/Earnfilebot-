import json

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_pool
from utils.qr import generate_qr_image
from utils.payment import create_invoice

router = Router()


# =========================
# SAFE PARSER BAYARGG
# =========================
def safe_data(res):
    if not isinstance(res, dict):
        return {}

    data = res.get("data")

    if isinstance(data, dict):
        return data

    if isinstance(data, str):
        try:
            return json.loads(data)
        except:
            return {}

    return {}

@router.callback_query(F.data.startswith("buy:"))
async def buy_handler(call: CallbackQuery):

    code = call.data.split(":")[1]
    user_id = call.from_user.id

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code=$1",
        code
    )

    if not file:
        return await call.answer("❌ File tidak ditemukan", show_alert=True)

    # =========================
    # SAFE PRICE
    # =========================
    try:
        amount = int(file.get("price") or 0)
    except:
        amount = 0

    # =========================
    # FREE FILE
    # =========================
    if amount <= 0:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📂 OPEN FILE",
                        callback_data=f"page:{code}:1"
                    )
                ]
            ]
        )

        await call.message.answer("🆓 FILE GRATIS", reply_markup=kb)
        return await call.answer()

    # =========================
    # CREATE INVOICE (FIXED INDENT)
    # =========================
    res = await create_invoice(amount, code, user_id)

    if not res:
        return await call.answer("❌ Gagal membuat invoice", show_alert=True)

    data = safe_data(res)

    qris = data.get("qris_string")
    pay_url = data.get("payment_url")

    if not qris and not pay_url:
        print("DEBUG BAYARGG:", res)
        return await call.answer("❌ Response BayarGG tidak valid", show_alert=True)

    # =========================
    # BUTTON
    # =========================
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 BAYAR SEKARANG",
                    url=pay_url or "https://www.bayar.gg"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ BACK",
                    callback_data=f"page:{code}:1"
                )
            ]
        ]
    )

    caption = (
        "💰 PEMBAYARAN FILE\n\n"
        "━━━━━━━━━━━━━━\n"
        f"📦 CODE: {code}\n"
        f"💵 PRICE: Rp {amount}\n\n"
    )

    # =========================
    # QRIS
    # =========================
    if qris:
        try:
            qr_img = generate_qr_image(qris)

            await call.message.answer_photo(
                qr_img,
                caption=caption + "📲 Scan QRIS atau klik tombol",
                reply_markup=kb
            )

        except Exception as e:
            await call.message.answer(
                caption + f"⚠️ QR ERROR: {e}",
                reply_markup=kb
            )
    else:
        await call.message.answer(
            caption + "🔗 QRIS tidak tersedia",
            reply_markup=kb
        )

    await call.answer()
