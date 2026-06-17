import asyncio
import logging
from aiogram import Bot

CHANNELS = [
    -1003712587847,
    -1004304319968
]


async def check_force_sub(bot: Bot, user_id: int) -> bool:

    for channel_id in CHANNELS:

        ok = False

        for _ in range(3):  # retry biar tidak false reject
            try:
                member = await bot.get_chat_member(channel_id, user_id)
                status = member.status

                if status in ("member", "administrator", "creator"):
                    ok = True
                    break

            except Exception as e:
                logging.warning(
                    f"Force sub error | channel={channel_id} | user={user_id} | error={e}"
                )

            await asyncio.sleep(0.7)

        if not ok:
            return False

    return True
