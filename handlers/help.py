import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

# =========================
# CACHE (biar super cepat)
# =========================
HELP_CACHE = {}

def get_cache(key):
    return HELP_CACHE.get(key)

def set_cache(key, value):
    HELP_CACHE[key] = value


# =========================
# LOADING ANIMATION
# =========================
async def loading(call: CallbackQuery):
    msg = await call.message.edit_text("⏳ Loading")
    await asyncio.sleep(0.4)
    await msg.edit_text("⏳ Loading .")
    await asyncio.sleep(0.4)
    await msg.edit_text("⏳ Loading ..")
    await asyncio.sleep(0.4)
    await msg.edit_text("⏳ Loading ...")
    return msg


# =========================
# MAIN HELP MENU
# =========================
@router.callback_query(F.data == "help")
async def help_menu(call: CallbackQuery):

    msg = await loading(call)

    text = (
        "━━━━━━━━━━━━━━\n"
        "❓ <b>HELP CENTER</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "Silakan pilih bantuan yang kamu butuhkan 👇"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("📤 Cara Upload File", callback_data="help_upfile")],
            [InlineKeyboardButton("📥 Cara Get File", callback_data="help_getfile")],
            [InlineKeyboardButton("💸 Cara Withdraw", callback_data="help_withdraw")],
            [InlineKeyboardButton("💰 Cara Cuan", callback_data="help_profit")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")]
        ]
    )

    await msg.edit_text(text, reply_markup=kb)
    await call.answer()


# =========================
# UPFILE HELP
# =========================
@router.callback_query(F.data == "help_upfile")
async def help_upfile(call: CallbackQuery):

    cached = get_cache("upfile")

    if not cached:
        cached = (
            "━━━━━━━━━━━━━━\n"
            "📤 <b>CARA UPLOAD FILE</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            "1. Masuk menu UPFILE\n"
            "2. Kirim file / link\n"
            "3. Tentukan harga\n"
            "4. System generate code otomatis\n"
            "5. Code bisa dijual ke buyer\n"
        )
        set_cache("upfile", cached)

    msg = await loading(call)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("🔙 Back", callback_data="help")]
        ]
    )

    await msg.edit_text(cached, reply_markup=kb)
    await call.answer()


# =========================
# GET FILE HELP
# =========================
@router.callback_query(F.data == "help_getfile")
async def help_getfile(call: CallbackQuery):

    cached = get_cache("getfile")

    if not cached:
        cached = (
            "━━━━━━━━━━━━━━\n"
            "📥 <b>CARA GET FILE</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            "1. Klik GET FILE\n"
            "2. Masukkan kode\n"
            "3. Jika GRATIS → langsung buka\n"
            "4. Jika BERBAYAR → lakukan payment\n"
            "5. File akan dikirim otomatis\n"
        )
        set_cache("getfile", cached)

    msg = await loading(call)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("🔙 Back", callback_data="help")]
        ]
    )

    await msg.edit_text(cached, reply_markup=kb)
    await call.answer()


# =========================
# WITHDRAW HELP
# =========================
@router.callback_query(F.data == "help_withdraw")
async def help_withdraw(call: CallbackQuery):

    cached = get_cache("withdraw")

    if not cached:
        cached = (
            "━━━━━━━━━━━━━━\n"
            "💸 <b>CARA WITHDRAW</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            "1. Masuk ACCOUNT\n"
            "2. Klik WITHDRAW\n"
            "3. Input nominal\n"
            "4. Tunggu proses\n"
            "5. Dana masuk ke wallet\n"
        )
        set_cache("withdraw", cached)

    msg = await loading(call)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("🔙 Back", callback_data="help")]
        ]
    )

    await msg.edit_text(cached, reply_markup=kb)
    await call.answer()


# =========================
# PROFIT HELP
# =========================
@router.callback_query(F.data == "help_profit")
async def help_profit(call: CallbackQuery):

    cached = get_cache("profit")

    if not cached:
        cached = (
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
        set_cache("profit", cached)

    msg = await loading(call)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("🔙 Back", callback_data="help")]
        ]
    )

    await msg.edit_text(cached, reply_markup=kb)
    await call.answer()
