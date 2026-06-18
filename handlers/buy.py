import json

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_pool
from utils.qr import generate_qr_image
from utils.payment import create_invoice   # ✅ FIX UTAMA DI SINI

router = Router()


# =========================
# SAFE PARSER BAYARGG RESPONSE
# =========================
def extract_data(res):
    if not res:
        return {}

    data = res.get("data")

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            return {}

    if isinstance(data, dict):
        return data

    return {}


# =========================
# BUY HANDLER
# =========================
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

    amount = int(file.get("price") or 0)

    if amount <= 0:
        return await call.answer("❌ File ini tidak berbayar", show_alert=True)

    # =========================
    # CREATE INVOICE
    # =========================
    res = await create_invoice(code, user_id, amount)

    if not res:
        return await call.answer("❌ Gagal membuat invoice", show_alert=True)

    data = extract_data(res)

    qris = data.get("qris_string")
    pay_url = (
        data.get("payment_url")
        or data.get("checkout_url")
        or data.get("invoice_url")
        or data.get("url")
    )

    if not qris and not pay_url:
        return await call.answer("❌ Response BayarGG tidak valid", show_alert=True)

    # =========================
    # BUTTON
    # =========================
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 BAYAR SEKARANG",
                    url=pay_url if pay_url else "https://www.bayar.gg"
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
    # QRIS IMAGE FIX (INI YANG BENAR)
    # =========================
    if qris:
        qr_img = generate_qr_image(qris)

        await call.message.answer_photo(
            qr_img,
            caption=caption + "📲 Scan QRIS atau klik tombol di bawah",
            reply_markup=kb
        )
    else:
        await call.message.answer(
            caption + "🔗 QRIS tidak tersedia, gunakan tombol di bawah",
            reply_markup=kb
        )

    await call.answer()
