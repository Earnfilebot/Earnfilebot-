from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.payment import create_bayargg_invoice

router = Router()


@router.message(Command("pay"))
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
        "✅ Invoice berhasil dibuat\n"
        f"🔗 {result['checkout_url']}\n"
        f"🧾 {result['reference']}"
    )
