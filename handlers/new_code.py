from aiogram import Router, F
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

from database import get_pool

router = Router()


# =========================
# MENU NEW CODE
# =========================
@router.callback_query(F.data == "new_code")
async def new_file(call: CallbackQuery):

    pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT
            code,
            media_count,
            created_at
        FROM files
        ORDER BY created_at DESC
        LIMIT 10
        """
    )


    if not rows:

        await call.message.answer(
            "❌ Belum ada code baru."
        )

        return await call.answer()



    text = (
        "🆕 <b>10 CODE TERBARU</b>\n"
        "━━━━━━━━━━━━━━━\n\n"
    )


    for i, row in enumerate(rows, start=1):

        created = row["created_at"]

        if created:
            waktu = created.strftime(
                "%d-%m-%Y %H:%M"
            )
        else:
            waktu = "-"


        text += (
            f"{i}. 🔑 <code>{row['code']}</code>\n"
            f"📦 Media : {row['media_count']} file\n"
            f"🕒 {waktu}\n\n"
        )


    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Kembali",
                    callback_data="home"
                )
            ]
        ]
    )


    await call.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


    await call.answer()
