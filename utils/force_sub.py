from aiogram import Bot

CHANNELS = [
    -1003712587847,
    -1003721009353
]

async def check_force_sub(bot: Bot, user_id: int):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)

            # hanya dianggap gagal kalau benar-benar keluar
            if member.status in ("left", "kicked"):
                return False

        except Exception:
            return False

    return True
