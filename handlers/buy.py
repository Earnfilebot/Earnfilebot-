import httpx
import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_pool
from config import BAYARGG_API_KEY, BAYARGG_MERCHANT

router = Router()


# =========================
# CREATE INVOICE BAYARGG
# =========================
async def create_invoice(code: str, user_id: int, amount: int):

    url = "https://api.bayargg.com/v1/transaction/create"

    payload = {
        "merchant": BAYARGG_MERCHANT,
        "apikey": BAYARGG_API_KEY,
        "amount": int(amount),
        "external_id": f"{user_id}_{code}",
        "callback_url": "https://earnfilebot.up.railway.app/bayargg/webhook"
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, json=payload)

        data = r.json()

        print("BAYARGG RESPONSE:", data)

        return data

    except Exception as e:
        print("CREATE INVOICE ERROR:", e)
        return None


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

    # =========================
    # IMPORT (HARUS DI ATAS BLOK INI)
    # =========================
    from utils.qris import extract_qris
    from utils.qr import generate_qr_image

    # =========================
    # QRIS IMAGE (BENAR POSISI)
    # =========================
    qris = extract_qris(res)

    if qris:
        qr_img = generate_qr_image(qris)

        await call.message.answer_photo(
            qr_img,
            caption="💳 Scan QRIS untuk pembayaran"
        )

    # =========================
    # SAFE PARSE RESPONSE
    # =========================
    data = res.get("data") or {}

    pay_url = (
        data.get("payment_url")
        or data.get("checkout_url")
        or data.get("url")
    )

    if not pay_url:
        return await call.answer("❌ Payment URL tidak ditemukan", show_alert=True)

    # =========================
    # BUTTON PAYMENT
    # =========================
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 BAYAR SEKARANG",
                    url=pay_url
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

    await call.message.answer(
        "💰 PEMBAYARAN FILE\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📦 CODE: {code}\n"
        f"💵 PRICE: {amount}\n\n"
        "Klik tombol di bawah untuk pembayaran",
        reply_markup=kb
    )

    await call.answer()
