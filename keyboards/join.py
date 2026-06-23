from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

def join_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢Channel Code",
                    url="https://t.me/+mp7HeZPteus0ZDQ9"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢Channel Update",
                    url="https://t.me/+JL4ELKQCyckwMjFl"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ CHECK",
                    callback_data="check_sub"
                )
            ]
        ]
    )
