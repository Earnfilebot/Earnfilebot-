from aiogram import Router, F
from aiogram.types import Message
from database import get_pool

router = Router()


@router.callback_query(F.data == "top_file")
async def top_file(call: CallbackQuery):

    pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT
            code,
            download_count,
            total_media,
            is_paid,
            price
        FROM files
        ORDER BY download_count DESC
        LIMIT 10
        """
    )


    if not rows:
        return await message.answer(
            "❌ Belum ada data code."
        )


    text = (
        "🏆 <b>TOP 10 CODE TERPOPULER</b>\n"
        "━━━━━━━━━━━━━━━\n\n"
    )


    for rank, row in enumerate(rows, start=1):

        status = "💰 VIP" if row["is_paid"] else "🆓 FREE"

        text += (
            f"{rank}. 🔑 <code>{row['code']}</code>\n"
            f"   {status}\n"
            f"   📥 Dibuka : {row['download_count']}x\n"
            f"   📦 Media : {row['total_media']} file\n\n"
        )


    await message.answer(
        text,
        parse_mode="HTML"
    )
