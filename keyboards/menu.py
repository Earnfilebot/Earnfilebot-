from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


def home_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Upload File",
                    callback_data="upfile"
                ),
                InlineKeyboardButton(
                    text="📥 Decode File",
                    callback_data="getfile"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👤 Account",
                    callback_data="account"
                ),
                InlineKeyboardButton(
                    text="💎 VVIP",
                    callback_data="vvip"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💸 Withdraw",
                    callback_data="withdraw"
                )
            ],
            [
                InlineKeyboardButton(
                    text="ℹ️ About",
                    callback_data="about"
                )
            ]
        ]
    )
