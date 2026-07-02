import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from utils.force_sub import check_force_sub
from keyboards.join import join_kb
from handlers.start import render_home_fast
from database import get_pool

router = Router()


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery):

    user_id = call.from_user.id
    logging.info(f"CHECK SUB CLICKED: {user_id}")

    try:
        ok = await check_force_sub(call.bot, user_id)
        logging.info(f"FORCE SUB RESULT: {ok}")

        if not ok:

            await call.answer(
                "❌ Kamu belum join semua channel.",
                show_alert=True
            )

            await call.message.edit_text(
                "❌ Kamu belum join semua channel.\n\nSilakan join dulu lalu klik CHECK lagi.",
                reply_markup=join_kb()
            )
            return

        pool = await get_pool()

        user = await pool.fetchrow(
            """
            SELECT username, balance
            FROM users
            WHERE telegram_id=$1
            """,
            user_id
        )

        await call.answer("✅ Verifikasi berhasil")

        await render_home_fast(
            call.bot,
            call.message,
            user_id,
            user["username"] or "unknown",
            user["balance"] or 0
        )

    except Exception as e:
        logging.exception(f"CHECK SUB ERROR: {e}")
        await call.answer("❌ SYSTEM ERROR", show_alert=True)
