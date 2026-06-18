from aiogram import Router, F
from aiogram.types import CallbackQuery

from utils.payment import create_bayargg_invoice
from database import get_pool

router = Router()


@router.callback_query(F.data.startswith("buy:"))
async def buy_access(call: CallbackQuery):
    code = call.data.split(":")[1]
    user_id = call.from_user.id

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT price FROM files WHERE code=$1",
        code
    )

    if not file:
        return await call.answer("❌ File tidak ditemukan", show_alert=True)

    price = int(file["price"] or 0)

    result = await create_bayargg_invoice(
        amount=price,
        code=code,
        user_id=user_id
    )

    if not result:
        return await call.answer("❌ Gagal buat invoice", show_alert=True)

    checkout = result.get("checkout_url")
    qris = result.get("qris_string")

    text = (
        "💳 INVOICE CREATED\n\n"
        f"🔗 Checkout: {checkout or '-'}\n"
        f"📦 CODE: {code}\n"
        f"💰 PRICE: {price}\n"
    )

    if qris:
        text += "\n⚡ QRIS ready"

    await call.message.edit_text(text)
    await call.answer()
