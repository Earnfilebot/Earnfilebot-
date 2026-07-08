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


    code = message.text.strip()


    pool = await get_pool()


    file = await pool.fetchrow(
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
        WHERE code=$1
        """,
        code
    )


    if not file:

        await state.clear()

        return await message.answer(
            "❌ CODE tidak ditemukan."
        )



    waktu = (
        file["created_at"].strftime(
            "%d-%m-%Y %H:%M"
        )
        if file["created_at"]
        else "-"
    )



    status = (
        f"💰 Berbayar Rp {file['price']:,}".replace(",", ".")
        if file["is_paid"]
        else "🆓 Gratis"
    )



    title = file["title"] or "-"

    category = file["category"] or "-"



    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="📥 Ambil File",
                    callback_data=f"page:{code}:1"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⬅️ Kembali",
                    callback_data="home"
                )
            ]

        ]
    )



    text = (
        "🔎 <b>CODE DITEMUKAN</b>\n"
        "━━━━━━━━━━━━━━━\n\n"

        f"📌 Judul : {title}\n"
        f"📂 Kategori : {category}\n\n"

        f"🔑 CODE:\n"
        f"<code>{file['code']}</code>\n\n"

        f"📦 Media : {file['media_count']} file\n"
        f"📥 Download : {file['download_count']}x\n"
        f"📌 Status : {status}\n"
        f"🕒 Dibuat : {waktu}"
    )



    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


    await state.clear()
