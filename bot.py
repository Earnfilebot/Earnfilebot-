import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import connect_db, close_db

# =========================
# HIDE AIROGRAM SPAM LOG
# =========================
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

# =========================
# ROUTERS
# =========================
from handlers.start import router as start_router
from handlers.check_sub import router as check_sub_router
from handlers.upfile import router as upfile_router
from handlers.getfile import router as getfile_router
from handlers.payment import router as payment_router
from handlers.page import router as page_router
from handlers.admin import router as admin_router

# =========================
# INIT
# =========================
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# =========================
# REGISTER ROUTERS
# =========================
dp.include_router(start_router)
dp.include_router(check_sub_router)
dp.include_router(upfile_router)
dp.include_router(getfile_router)
dp.include_router(payment_router)
dp.include_router(page_router)
dp.include_router(admin_router)

# =========================
# START BOT
# =========================
async def main():

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    await connect_db()
    print("DATABASE CONNECTED")

    try:

        print("BOT STARTED")

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )

    finally:

        await close_db()
        await bot.session.close()

        print("BOT STOPPED")


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    asyncio.run(main())
