import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

HELP_CACHE = {}


def get_cache(key):
    return HELP_CACHE.get(key)


def set_cache(key, value):
    HELP_CACHE[key] = value


async def loading(call: CallbackQuery):
    try:
        await call.message.edit_text("⏳ Loading...")
    except:
        pass
    await asyncio.sleep(0.3)


def kb_builder(buttons):
    builder = InlineKeyboardBuilder()

    for text, data in buttons:
        builder.button(text=text, callback_data=data)

    builder.adjust(1)
    return builder.as_markup()


# =========================
# HELP MENU
# =========================
@router.callback_query(F.data == "help")
async def help_menu(call: CallbackQuery):

    await loading(call)

    text = (
        "━━━━━━━━━━━━━━\n"
        "❓ <b>HELP CENTER</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "Silakan pilih bantuan yang kamu butuhkan 👇"
    )

    kb = kb_builder([
        ("📤 Cara Upload File", "help_upfile"),
        ("📥 Cara Get File", "help_getfile"),
        ("💎 VVIP Info", "help_vvip"),
        ("🏠 Home", "home"),
    ])

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# =========================
# TEMPLATE
# =========================
async def help_template(call: CallbackQuery, key: str, content: str):

    cached = get_cache(key)

    if cached is None:
        set_cache(key, content)
        cached = content

    await loading(call)

    kb = kb_builder([
        ("🔙 Back", "help")
    ])

    await call.message.edit_text(cached, reply_markup=kb)
    await call.answer()


# =========================
# UPFILE
# =========================
@router.callback_query(F.data == "help_upfile")
async def help_upfile(call: CallbackQuery):

    await help_template(
        call,
        "upfile",
        "━━━━━━━━━━━━━━\n"
        "📤 <b>CARA UPLOAD FILE</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "1. Masuk menu UPFILE\n"
        "2. Kirim file / link\n"
        "3. Tentukan harga\n"
        "4. System generate code otomatis\n"
        "5. Code digunakan untuk akses file\n"
    )


# =========================
# GET FILE
# =========================
@router.callback_query(F.data == "help_getfile")
async def help_getfile(call: CallbackQuery):

    await help_template(
        call,
        "getfile",
        "━━━━━━━━━━━━━━\n"
        "📥 <b>CARA GET FILE</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "1. Klik GET FILE\n"
        "2. Masukkan kode\n"
        "3. Jika GRATIS → langsung akses\n"
        "4. Jika BERBAYAR → lakukan unlock\n"
        "5. File akan dikirim otomatis\n"
    )


# =========================
# VVIP
# =========================
@router.callback_query(F.data == "help_vvip")
async def help_vvip(call: CallbackQuery):

    await help_template(
        call,
        "vvip",
        "━━━━━━━━━━━━━━\n"
        "💎 <b>VVIP SYSTEM</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "🔥 VVIP adalah akses premium user\n\n"
        "📌 Manfaat VVIP:\n"
        "• Update fitur lebih cepat\n"
        "• Akses fitur eksklusif\n"
        "• Support prioritas admin\n"
        "• Tutorial sampai paham\n"
        "• Sistem lebih stabil & prioritas server\n\n"
        "🚀 VVIP dibuat untuk user yang serius menggunakan bot"
    )
