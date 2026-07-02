from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from database import get_pool


class BanMiddleware(BaseMiddleware):

    async def __call__(self, handler, event, data):

        if isinstance(event, Message):
            telegram_id = event.from_user.id

        elif isinstance(event, CallbackQuery):
            telegram_id = event.from_user.id

        else:
            return await handler(event, data)

        pool = await get_pool()

        user = await pool.fetchrow(
            """
            SELECT is_banned
            FROM users
            WHERE telegram_id=$1
            """,
            telegram_id
        )

        if user and user["is_banned"]:

            if isinstance(event, Message):
                await event.answer(
                    "🚫 Akun Anda telah diblokir oleh admin."
                )

            else:
                await event.answer(
                    "🚫 Akun Anda diblokir.",
                    show_alert=True
                )

            return

        return await handler(event, data)
