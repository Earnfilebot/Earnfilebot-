from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()


# =========================
# LOADING
# =========================
async def loading(call: CallbackQuery):
    try:
        await call.message.edit_text("⏳ Loading...")
    except:
        pass


# =========================
# SEARCH MENU
# =========================
@router.callback_query(F.data == "search")
async def search_menu(call: CallbackQuery):

    await loading(call)

    text = (
        "━━━━━━━━━━━━━━\n"
        "🔍 <b>PENCARIAN FILE</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "Temukan file yang kamu inginkan melalui menu di bawah ini.\n\n"
        "🔥 Top Terlaris\n"
        "👀 Top Dibuka\n"
        "🆕 File Terbaru\n"
        "🆓 File Gratis\n"
        "💰 File Berbayar\n"
        "🔎 Cari Judul\n"
        "📂 Semua File"
    )

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🔥 Top 5 Terlaris",
        callback_data="search_top_sold"
    )

    kb.button(
        text="👀 Top 5 Dibuka",
        callback_data="search_top_view"
    )

    kb.button(
        text="🆕 File Terbaru",
        callback_data="search_new"
    )

    kb.button(
        text="🆓 File Gratis",
        callback_data="search_free"
    )

    kb.button(
        text="💰 File Berbayar",
        callback_data="search_paid"
    )

    kb.button(
        text="🔎 Cari Judul",
        callback_data="search_title"
    )

    kb.button(
        text="📂 Semua File",
        callback_data="search_all:1"
    )

    kb.button(
        text="🔙 Kembali",
        callback_data="home"
    )

    kb.adjust(1)

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()


# =========================
# PLACEHOLDER
# =========================
@router.callback_query(
    F.data.in_({
        "search_top_sold",
        "search_top_view",
        "search_new",
        "search_free",
        "search_paid",
        "search_title"
    })
)
async def placeholder(call: CallbackQuery):

    await call.answer(
        "🚧 Fitur ini sedang dimuat...",
        show_alert=False
    )
