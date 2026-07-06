from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


class PaymentKeyboard:

    @staticmethod
    def invoice(invoice_id: str) -> InlineKeyboardMarkup:

        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Check Payment",
                        callback_data=f"check:{invoice_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Cancel",
                        callback_data=f"cancel:{invoice_id}"
                    )
                ]
            ]
        )
