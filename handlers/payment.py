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
        return await message.answer("❌ Gagal membuat invoice")

    checkout = result.get("checkout_url")
    reference = result.get("reference")
    qris = result.get("qris_string")

    text = (
        "✅ INVOICE CREATED\n\n"
        f"🔗 Checkout: {checkout or '-'}\n"
        f"🧾 Reference: {reference or '-'}\n"
    )

    # kalau QRIS ada → kasih info tambahan
    if qris:
        text += "\n⚡ QRIS tersedia (ready untuk auto unlock system)"

    await message.answer(text)
