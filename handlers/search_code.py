from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_pool


router = Router()


# =========================
# STATE
# =========================

class SearchCodeState(StatesGroup):
    waiting_code = State()



# =========================
# BUTTON SEARCH CODE
# =========================

@router.callback_query(F.data == "search_code")
async def search_start(
    call: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        SearchCodeState.waiting_code
    )


    await call.message.answer(
        "🔎 <b>SEARCH CODE</b>\n"
        "━━━━━━━━━━━━━━━\n\n"
        "Silakan masukkan CODE file.\n\n"
        "Contoh:\n"
        "<code>DecoderFileBot9KLWL057NH</code>",
        parse_mode="HTML"
    )


    await call.answer()



# =========================
# PROCESS SEARCH
# =========================

@router.message(SearchCodeState.waiting_code)
async def search_process(
    message: Message,
    state: FSMContext
):

    if not message.text:
        return


    keyword = message.text.strip()


    pool = await get_pool()


    files = await pool.fetch(
        """
        SELECT
            code,
            title,
            category,
            media_count,
            download_count,
            created_at,
            is_paid,
            price
        FROM files
        WHERE
            code ILIKE $1
            OR title ILIKE $1
            OR category ILIKE $1
        ORDER BY created_at DESC
        LIMIT 20
        """,
        f"%{keyword}%"
    )


    await state.clear()


    if not files:

        return await message.answer(
            "❌ Tidak ada file yang cocok."
        )



    text = (
        "🔎 <b>HASIL PENCARIAN</b>\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"Keyword : <code>{keyword}</code>\n\n"
    )


    buttons = []


    for i, file in enumerate(files, 1):

        title = file["title"] or "-"

        category = file["category"] or "-"


        status = (
            f"💰 Rp {file['price']:,}".replace(",", ".")
            if file["is_paid"]
            else "🆓 Gratis"
        )


        text += (
            f"<b>{i}. {title}</b>\n"
            f"📂 {category}\n"
            f"🔑 <code>{file['code']}</code>\n"
            f"📦 {file['media_count']} file\n"
            f"📌 {status}\n\n"
        )


        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📥 Ambil {i}",
                    callback_data=f"page:{file['code']}:1"
                )
            ]
        )



    buttons.append(
        [
            InlineKeyboardButton(
                text="⬅️ Kembali",
                callback_data="home"
            )
        ]
    )


    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )
