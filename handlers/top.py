from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from database import get_pool

router = Router()


# =========================
# MENU TOP FILE
# =========================
@router.callback_query(F.data == "top_file")
async def top_file(call: CallbackQuery):

    pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT
            code,
            download_count,
            media_count,
            is_paid,
            price
        FROM files
        ORDER BY download_count DESC
        LIMIT 10
        """
    )


    if not rows:

        await call.message.answer(
            "❌ Belum ada data code."
        )

        return await call.answer()



    text = (
        "🏆 <b>TOP 10 CODE TERPOPULER</b>\n"
        "━━━━━━━━━━━━━━━\n\n"
    )


    for rank, row in enumerate(rows, start=1):

        status = (
            "💰 PAID"
            if row["is_paid"]
            else
            "🆓 FREE"
        )


        text += (
            f"{rank}. 🔑 <code>{row['code']}</code>\n"
            f"   {status}\n"
            f"   📥 Dibuka : {row['download_count']}x\n"
            f"   📦 Media : {row['media_count']} file\n\n"
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
