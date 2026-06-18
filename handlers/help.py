import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

# =========================
# CACHE
# =========================
HELP_CACHE = {}

def get_cache(key):
    return HELP_CACHE.get(key)

def set_cache(key, value):
    HELP_CACHE[key] = value


# =========================
# LOADING (LEBIH RINGAN)
# =========================
async def loading(call: CallbackQuery):
    await call.message.edit_text("⏳ Loading...")
    await asyncio.sleep(0.5)


# =========================
# KEYBOARD HELPER
# =========================
def kb_builder(buttons):
    builder = InlineKeyboardBuilder()

    for text, data in buttons:
        builder.button(text=text, callback_data=data)

    builder.adjust(1)
    return builder.as_markup()


# =========================
# MAIN HELP MENU
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
        ("💸 Cara Withdraw", "help_withdraw"),
        ("💰 Cara Cuan", "help_profit"),
        ("🏠 Home", "home"),
    ])

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# =========================
# TEMPLATE FUNCTION (BIAR GAK NGULANG)
# =========================
async def help_template(call: CallbackQuery, key: str, content: str):

    cached = get_cache(key)

    if not cached:
        cached = content
        set_cache(key, cached)

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
    await help_template(call, "upfile",
        "━━━━━━━━━━━━━━\n"
        "📤 <b>CARA UPLOAD FILE</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "1. Masuk menu UPFILE\n"
        "2. Kirim file / link\n"
        "3. Tentukan harga\n"
        "4. System generate code otomatis\n"
        "5. Code bisa dijual ke buyer\n"
    )


# =========================
# GET FILE
# =========================
@router.callback_query(F.data == "help_getfile")
async def help_getfile(call: CallbackQuery):
    await help_template(call, "getfile",
        "━━━━━━━━━━━━━━\n"
        "📥 <b>CARA GET FILE</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "1. Klik GET FILE\n"
        "2. Masukkan kode\n"
        "3. Jika GRATIS → langsung buka\n"
        "4. Jika BERBAYAR → lakukan payment\n"
        "5. File akan dikirim otomatis\n"
    )


# =========================
# WITHDRAW
# =========================
@router.callback_query(F.data == "help_withdraw")
async def help_withdraw(call: CallbackQuery):
    await help_template(call, "withdraw",
        "━━━━━━━━━━━━━━\n"
        "💸 <b>CARA WITHDRAW</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "1. Masuk ACCOUNT\n"
        "2. Klik WITHDRAW\n"
        "3. Input nominal\n"
        "4. Tunggu proses\n"
        "5. Dana masuk ke wallet\n"
    )


# =========================
# PROFIT
# =========================
@router.callback_query(F.data == "help_profit")
async def help_profit(call: CallbackQuery):
    await help_template(call, "profit",
        "━━━━━━━━━━━━━━\n"
        "💰 <b>CARA MENGHASILKAN CUAN</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "1. Upload file / code\n"
        "2. Set harga jual\n"
        "3. Dapatkan kode produk\n"
        "4. Share ke buyer\n"
        "5. Setiap transaksi → saldo masuk otomatis\n\n"
        "🚀 Semakin banyak produk → semakin besar income"
    )
