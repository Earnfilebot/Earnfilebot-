from utils.force_sub import check_force_sub

async def force_guard(bot, user_id):
    return await check_force_sub(bot, user_id)
