from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

def join_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Channel 1",
                    url="https://t.me/+JL4ELKQCyckwMjFl"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Channel 2",
                    url="https://t.me/+TiCdabQsYW43Mjk1"
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
