from aiogram import Router
from aiogram.types import Message, CallbackQuery, InlineQuery
from database import get_pool

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

    # maintenance OFF → jangan ganggu router lain
    if not await is_maintenance():
        return

    # admin bebas akses
    if is_admin(message.from_user.id):
        return

    text = await get_maintenance_text()

    try:
        await message.delete()
    except Exception:
        pass

    await message.answer(text)


# =========================
# CALLBACK BLOCK
# =========================
@router.callback_query()
async def block_callback(call: CallbackQuery):

    if not await is_maintenance():
        return

    if is_admin(call.from_user.id):
        return

    text = await get_maintenance_text()

    await call.answer(
        text,
        show_alert=True
    )


# =========================
# INLINE BLOCK
# =========================
@router.inline_query()
async def block_inline(query: InlineQuery):

    if not await is_maintenance():
        return

    if is_admin(query.from_user.id):
        return

    await query.answer(
        results=[],
        cache_time=1,
        is_personal=True,
        switch_pm_text="🚧 Bot sedang maintenance",
        switch_pm_parameter="start"
    )
