import httpx
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
        "amount": amount,
        "external_id": f"{code}:{user_id}",
        "callback_url": "https://yourdomain.com/webhook/bayargg"
    }

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, json=payload)
        return r.json()


# =========================
# BUY HANDLER
# =========================
@router.callback_query(F.data.startswith("buy:"))
async def buy_handler(call: CallbackQuery):

    try:
        _, code = call.data.split(":")
    except:
        return await call.answer("❌ Invalid data", show_alert=True)

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT * FROM files WHERE code=$1",
        code
    )

    if not file:
        return await call.answer("❌ File tidak ditemukan", show_alert=True)

    user_id = call.from_user.id

    # =========================
    # ANTI DOUBLE BUY (basic)
    # =========================
    buyers = file.get("buyers")

    if buyers:
        if isinstance(buyers, str):
            try:
                import json
                buyers = json.loads(buyers)
            except:
                buyers = []

    if not buyers:
        buyers = []

    if user_id in buyers:
        return await call.answer("✔ Sudah pernah membeli", show_alert=True)

    amount = file.get("price", 0)

    if amount <= 0:
        return await call.answer("❌ File ini gratis", show_alert=True)

    # =========================
    # CREATE INVOICE
    # =========================
    res = await create_invoice(code, user_id, amount)

    if not res or not res.get("status"):
        return await call.answer("❌ Gagal membuat pembayaran", show_alert=True)

    pay_url = res["data"]["payment_url"]

    # =========================
    # PAYMENT BUTTON
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
        "Klik tombol di bawah untuk melakukan pembayaran\n"
        "Setelah bayar, file akan otomatis terbuka",
        reply_markup=kb
    )

    await call.answer()
