from aiogram import Router
from aiogram.types import Message, CallbackQuery, InlineQuery
from database import get_pool

# ✅ IMPORT LANGSUNG (FIX)
from handlers.admin.admins import is_admin

router = Router()


# =========================
# GET STATUS
# =========================
async def is_maintenance():
    pool = await get_pool()
    val = await pool.fetchval(
        "SELECT value FROM settings WHERE key='maintenance'"
    )
    return val == "on"


async def get_maintenance_text():
    pool = await get_pool()
    val = await pool.fetchval(
        "SELECT value FROM settings WHERE key='maintenance_text'"
    )
    return val or "🚧 Bot sedang maintenance, coba lagi nanti."


# =========================
# MESSAGE BLOCK
# =========================
@router.message()
async def block_message(message: Message):
    if await is_maintenance() and not is_admin(message.from_user.id):
        text = await get_maintenance_text()

        try:
            await message.delete()
        except:
            pass

        return await message.answer(text)


# =========================
# CALLBACK BLOCK
# =========================
@router.callback_query()
async def block_callback(call: CallbackQuery):
    if await is_maintenance() and not is_admin(call.from_user.id):
        text = await get_maintenance_text()
        await call.answer(text, show_alert=True)
        return


# =========================
# INLINE QUERY BLOCK
# =========================
@router.inline_query()
async def block_inline(query: InlineQuery):
    if await is_maintenance() and not is_admin(query.from_user.id):
        await query.answer(
            results=[],
            cache_time=1,
            is_personal=True,
            switch_pm_text="🚧 Bot sedang maintenance",
            switch_pm_parameter="start"
        )
