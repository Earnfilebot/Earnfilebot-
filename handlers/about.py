from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):

    text = (
        "━━━━━━━━━━━━━━\n"
        "ℹ️ <b>ABOUT EARNFILEBOX BOT</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "🤖 <b>Name</b>    : EarnFileBox Bot\n"
        "⚙️ <b>Version</b> : 1.0 (SaaS MVP)\n"
        "📦 <b>Type</b>    : Digital Product Marketplace System\n\n"
        "━━━━━━━━━━━━━━\n"
        "💡 <b>WHAT IS THIS BOT?</b>\n"
        "EarnFileBoxBot adalah platform otomatis\n"
        "untuk jual & distribusi digital code / file\n"
        "dengan sistem pembayaran QRIS & unlock otomatis.\n\n"
        "━━━━━━━━━━━━━━\n"
        "💰 <b>MONETIZATION SYSTEM</b>\n"
        "• Jual code / file digital\n"
        "• Auto unlock setelah payment\n"
        "• Tracking transaksi real-time\n"
        "• Dashboard income & balance\n\n"
        "━━━━━━━━━━━━━━\n"
        "🚀 <b>FEATURES</b>\n"
        "• File/code marketplace\n"
        "• QRIS payment integration\n"
        "• User account dashboard\n"
        "• Transaction history system\n"
        "• Top product analytics\n\n"
        "━━━━━━━━━━━━━━\n"
        "🛠 <b>DEVELOPMENT STATUS</b>\n"
        "Version ini masih dalam tahap pengembangan (MVP).\n"
        "Fitur akan terus ditingkatkan menuju SaaS full system:\n"
        "• Anti fraud system\n"
        "• Auto payout withdraw\n"
        "• Advanced analytics\n"
        "• Multi seller support\n\n"
        "━━━━━━━━━━━━━━\n"
        "🔥 <b>GOAL</b>\n"
        "Menjadikan bot ini sebagai sistem SaaS\n"
        "untuk menghasilkan cuan dari digital product marketplace."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏠 Home", callback_data="home"),
                InlineKeyboardButton(text="💼 Account", callback_data="account")
            ]
        ]
    )

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()
