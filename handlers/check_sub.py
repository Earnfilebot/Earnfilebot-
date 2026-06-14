from aiogram import Router, F
from aiogram.types import CallbackQuery

from utils.force_sub import check_force_sub
from keyboards.menu import home_kb
from keyboards.join import join_kb

router = Router()


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery):

    user_id = call.from_user.id

    # FORCE SUB CHECK
    if not await check_force_sub(call.bot, user_id):

        await call.answer(
            "❌ Kamu belum join semua channel.",
            show_alert=True
        )

        await call.message.edit_text(
            "❌ Kamu belum join semua channel.\n\nSilakan join dulu lalu klik CHECK lagi.",
            reply_markup=join_kb()
        )

        return

    # HOME TEXT (konsisten dengan START)
    text = f"""
𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧

🆔 𝗜𝗗 : {user_id}
💰 𝗕𝗔𝗟𝗔𝗡𝗖𝗘 : Rp0

━━━━━━━━━━━━━━
𝗖𝗢𝗣𝗬𝗥𝗜𝗚𝗛𝗧 𝗘𝗔𝗥𝗡𝗙𝗜𝗟𝗘𝗕𝗢𝗧
"""

    # SAFE EDIT MESSAGE
    try:
        await call.message.edit_text(
            text,
            reply_markup=home_kb()
        )
    except Exception:
        await call.message.answer(
            text,
            reply_markup=home_kb()
        )
