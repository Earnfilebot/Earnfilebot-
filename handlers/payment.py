from aiogram import Router
from aiogram.types import Message

from utils.payment import create_bayargg_invoice

router = Router()


# =========================
# TEST PAYMENT COMMAND
# =========================
@router.message()
async def test_payment(message: Message):
    result = await create_bayargg_invoice(
        amount=10000,
        code="TEST",
        user_id=message.from_user.id
    )

    if not result:
        await message.answer("❌ Gagal membuat invoice")
        return

    await message.answer(
        "✅ Invoice berhasil dibuat\n\n"
        f"🔗 Link: {result['checkout_url']}\n"
        f"🧾 Ref: {result['reference']}"
    )
