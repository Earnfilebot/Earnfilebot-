from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

def home_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 UPFILE",
                    callback_data="upfile"
                ),
                InlineKeyboardButton(
                    text="📥 GETFILE",
                    callback_data="getfile"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👤 ACCOUNT",
                    callback_data="account"
                ),
                InlineKeyboardButton(
                    text="💸 WITHDRAW",
                    callback_data="withdraw"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❓ HELP",
                    callback_data="help"
                ),
                InlineKeyboardButton(
                    text="ℹ️ ABOUT",
                    callback_data="about"
                )
            ]
        ]
    )
