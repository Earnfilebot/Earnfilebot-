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

class SearchPriceState(StatesGroup):
    waiting_price = State()



# =========================
# BUTTON SEARCH PRICE
# =========================

@router.callback_query(F.data == "search_price")
async def search_price_start(
    call: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        SearchPriceState.waiting_price
    )


    await call.message.answer(
        "💰 <b>SEARCH HARGA</b>\n"
        "━━━━━━━━━━━━━━━\n\n"
        "Masukkan harga file.\n\n"
        "Contoh:\n"
        "<code>5000</code>",
        parse_mode="HTML"
    )


    await call.answer()



# =========================
# PROCESS SEARCH PRICE
# =========================

@router.message(SearchPriceState.waiting_price)
async def search_price_process(
    message: Message,
    state: FSMContext
):

    try:

        price = int(
            message.text.replace(".", "")
            .replace(",", "")
            .strip()
        )

    except:

        return await message.answer(
            "❌ Harga harus angka.\n\n"
            "Contoh:\n"
            "<code>5000</code>",
            parse_mode="HTML"
        )



    pool = await get_pool()



    rows = await pool.fetch(
        """
        SELECT
            code,
            title,
            category,
            media_count,
            price,
            is_paid,
            created_at
        FROM files
        WHERE price=$1
        ORDER BY created_at DESC
        LIMIT 20
        """,
        price
    )



    if not rows:

        await state.clear()

        return await message.answer(
            "❌ Tidak ada file dengan harga tersebut."
        )



    text = (
        "💰 <b>HASIL SEARCH HARGA</b>\n"
        "━━━━━━━━━━━━━━━\n\n"
    )



    buttons = []



    for i, row in enumerate(rows, start=1):

        title = row["title"] or "-"

        category = row["category"] or "-"


        text += (
            f"{i}. 🔑 <code>{row['code']}</code>\n"
            f"📌 Judul : {title}\n"
            f"📂 Kategori : {category}\n"
            f"📦 Media : {row['media_count']} file\n"
            f"💵 Harga : Rp {row['price']:,}\n\n"
            .replace(",", ".")
        )


        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📥 {i}. Ambil File",
                    callback_data=f"page:{row['code']}:1"
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



    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons
    )



    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )



    await state.clear()
