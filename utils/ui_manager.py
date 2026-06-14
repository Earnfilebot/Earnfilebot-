USER_UI = {}


async def set_ui(user_id: int, chat_id: int, message_id: int):
    USER_UI[user_id] = {
        "chat_id": chat_id,
        "message_id": message_id
    }


async def get_ui(user_id: int):
    return USER_UI.get(user_id)


async def delete_ui(bot, user_id: int):
    ui = USER_UI.get(user_id)
    if not ui:
        return

    try:
        await bot.delete_message(
            chat_id=ui["chat_id"],
            message_id=ui["message_id"]
        )
    except:
        pass

    USER_UI.pop(user_id, None)


async def update_ui(bot, user_id: int, text: str, reply_markup=None):

    ui = USER_UI.get(user_id)

    if not ui:
        return None

    try:
        return await bot.edit_message_text(
            chat_id=ui["chat_id"],
            message_id=ui["message_id"],
            text=text,
            reply_markup=reply_markup
        )

    except:
        # 🔥 fallback kalau message expired / dihapus
        USER_UI.pop(user_id, None)
        return None
