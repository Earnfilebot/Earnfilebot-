import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

CHANNELS = [
    -1004395938795,
    -1003712587847
]


async def check_force_sub(bot: Bot, user_id: int) -> bool:

    for channel_id in CHANNELS:

        try:
            member = await bot.get_chat_member(channel_id, user_id)
            status = member.status

            if status not in ("member", "administrator", "creator"):
                return False

        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logging.warning(
                f"Force sub API error | channel={channel_id} | user={user_id} | {e}"
            )
            # ⚠️ fallback: jangan blok user karena API error
            return True

        except Exception as e:
            logging.warning(
                f"Force sub unknown error | channel={channel_id} | user={user_id} | {e}"
            )
            return True

    return True
