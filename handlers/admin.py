from aiogram import Router
from aiogram.types import Message
from database import get_pool

router = Router()


@router.message(lambda m: m.text == "/stats")
async def stats(message: Message):
    pool = await get_pool()

    users = await pool.fetchval("SELECT COUNT(*) FROM users")
    sales = await pool.fetchval("SELECT COUNT(*) FROM payments WHERE status='paid'")
    revenue = await pool.fetchval("""
        SELECT COALESCE(SUM(amount),0)
        FROM payments
        WHERE status='paid'
    """)

    await message.answer(
        "📊 ADMIN STATS\n"
        "━━━━━━━━━━━━━━\n\n"
        f"👤 Users  : {users}\n"
        f"💰 Sales  : {sales}\n"
        f"📈 Revenue: Rp{revenue:,}\n"
    )
