from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_pool

router = Router()


class SearchCodeState(StatesGroup):
    waiting_code = State()


# =========================
# BUTTON SEARCH CODE
# =========================

@router.message(F.text == "🔎 Search Code")
async def search_start(
    message: Message,
    state: FSMContext
):

    await state.set_state(
        SearchCodeState.waiting_code
    )

    await message.answer(
        "🔎 <b>Masukkan CODE</b>\n\n"
        "Contoh:\n"
        "<code>DecoderFileBot9KLWL057NH</code>",
        parse_mode="HTML"
    )


# =========================
# PROCESS SEARCH
# =========================

@router.message(SearchCodeState.waiting_code)
async def search_process(
    message: Message,
    state: FSMContext
):

    code = message.text.strip()

    pool = await get_pool()


    file = await pool.fetchrow(
        """
        SELECT
            code,
            title,
            category,
            total_media,
            download_count,
            created_at,
            is_paid
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


    waktu = file["created_at"].strftime(
        "%d-%m-%Y %H:%M"
    )


    status = (
        "💰 Berbayar"
        if file["is_paid"]
        else
        "🆓 Gratis"
    )


    title = (
        file["title"]
        if file["title"]
        else
        "-"
    )

    category = (
        file["category"]
        if file["category"]
        else
        "-"
    )


    kb = InlineKeyboardMarkup(
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


    await message.answer(
        "🔎 <b>CODE DITEMUKAN</b>\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"📌 Judul : {title}\n"
        f"📂 Kategori : {category}\n\n"
        f"🔑 CODE:\n"
        f"<code>{file['code']}</code>\n\n"
        f"📦 Media : {file['total_media']} file\n"
        f"📥 Download : {file['download_count']}x\n"
        f"📌 Status : {status}\n"
        f"🕒 Dibuat : {waktu}",
        parse_mode="HTML",
        reply_markup=kb
    )


    await state.clear()
