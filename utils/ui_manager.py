from utils.ui import USER_UI

async def update_ui(bot, user_id: int, text: str, reply_markup=None):

    if user_id not in USER_UI:
        return

    data = USER_UI[user_id]

    try:
        await bot.edit_message_text(
            chat_id=data["chat_id"],
            message_id=data["message_id"],
            text=text,
            reply_markup=reply_markup
        )
    except:
        # kalau message hilang / expired → ignore
        pass
