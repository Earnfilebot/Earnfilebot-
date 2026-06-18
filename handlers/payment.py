from aiogram import Router, F
from aiogram.types import CallbackQuery

from utils.payment import create_bayargg_invoice
from database import get_pool

router = Router()


@router.callback_query(F.data.startswith("buy:"))
async def buy(call: CallbackQuery):
    code = call.data.split(":")[1]
    user_id = call.from_user.id

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT price FROM files WHERE code=$1",
        code
    )

    price = int(file["price"])

    result = await create_bayargg_invoice(price, code, user_id)

    if not result:
        return await call.answer("❌ invoice gagal", show_alert=True)

    qris = result.get("qris_string")
    checkout = result.get("checkout_url")

    text = f"""
💳 INVOICE CREATED

📦 CODE: {code}
💰 PRICE: {price}

"""

    if qris:
        text += f"\n📲 QRIS:\n`{qris}`"
    else:
        text += f"\n🔗 PAY LINK:\n{checkout}"

    await call.message.edit_text(text)
    await call.answer()
