from aiogram import Bot

CHANNELS = [
    -1003712587847,
    -1003721009353
]


async def check_force_sub(
    bot: Bot,
    user_id: int
) -> bool:

    for channel_id in CHANNELS:

        try:

            member = await bot.get_chat_member(
                channel_id,
                user_id
            )

            if member.status not in (
                "member",
                "administrator",
                "creator"
            ):
                return False

        except Exception:
            return False

    return True
