from aiogram import Router, F
from aiogram.types import (
    Message,
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
            total_media,
            created_at
        FROM files
        ORDER BY created_at DESC
        LIMIT 10
        """
    )


    if not rows:

        return await message.answer(
            "❌ Belum ada code baru."
        )


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
            f"📦 Media : {row['total_media']} file\n"
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


    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

