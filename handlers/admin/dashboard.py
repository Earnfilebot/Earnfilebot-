from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_pool
from config import ADMIN_IDS

from datetime import datetime
import pytz


router = Router()


# =========================
# ADMIN CHECK
# =========================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS



# =========================
# RUPIAH FORMAT
# =========================

def rupiah(value):

    try:
        value = int(value or 0)
    except:
        value = 0

    return f"Rp {value:,}".replace(",", ".")



# =========================
# ADMIN KEYBOARD
# =========================

def admin_keyboard():

    kb = InlineKeyboardBuilder()


    kb.button(
        text="👤 Users",
        callback_data="admin_users"
    )

    kb.button(
        text="📂 Files",
        callback_data="admin_files"
    )

    kb.button(
        text="📢 Broadcast",
        callback_data="admin_broadcast"
    )

    kb.button(
        text="💳 Payment",
        callback_data="admin_payment"
    )

    kb.button(
        text="🏧 Withdraw",
        callback_data="admin_withdraw"
    )

    kb.button(
        text="💰 Balance",
        callback_data="admin_balance"
    )

    kb.button(
        text="📊 Statistik",
        callback_data="admin_stats"
    )

    kb.button(
        text="📝 Logs",
        callback_data="admin_logs"
    )

    kb.button(
        text="⚙️ Settings",
        callback_data="admin_settings"
    )


    kb.adjust(2)


    return kb.as_markup()



# =========================
# DASHBOARD TEXT
# =========================

async def dashboard_text():

    pool = await get_pool()


    users = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM users
        """
    ) or 0


    files = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM codes
        """
    ) or 0


    media = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM medias
        """
    ) or 0



    tz = pytz.timezone(
        "Asia/Jakarta"
    )

    update = datetime.now(tz).strftime(
        "%d-%m-%Y %H:%M"
    )


    return f"""
🛠 <b>ADMIN PANEL</b>
━━━━━━━━━━━━━━━━━━

📊 <b>SYSTEM</b>

👤 Users  : {users}
📂 Files  : {files}
🖼 Media  : {media}

━━━━━━━━━━━━━━━━━━

⚡ Status : Online

🕒 Update : {update} WIB
"""



# =========================
# COMMAND /ADMIN
# =========================

@router.message(Command("admin"))
async def admin_command(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return


    text = await dashboard_text()


    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )



# =========================
# CALLBACK HOME
# =========================

@router.callback_query(
    lambda c: c.data == "admin_home"
)
async def admin_home(
    call: CallbackQuery
):

    if not is_admin(
        call.from_user.id
    ):
        return await call.answer(
            "❌ No Access",
            show_alert=True
        )


    text = await dashboard_text()


    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


    await call.answer()
