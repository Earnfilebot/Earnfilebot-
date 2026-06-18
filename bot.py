import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from fastapi import FastAPI
import uvicorn

from config import BOT_TOKEN
from database import connect_db, close_db


# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)


# =========================
# BOT INIT
# =========================
bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)

dp = Dispatcher()


# =========================
# ROUTERS (AIROGRAM ONLY)
# =========================
from handlers.start import router as start_router
from handlers.check_sub import router as check_sub_router
from handlers.upfile import router as upfile_router
from handlers.getfile import router as getfile_router
from handlers.buy import router as buy_router
from handlers.page import router as page_router
from handlers.account import router as account_router
from handlers.withdraw import router as withdraw_router
from handlers.help import router as help_router
from handlers.about import router as about_router
from handlers.admin import router as admin_router


dp.include_router(start_router)
dp.include_router(check_sub_router)
dp.include_router(upfile_router)
dp.include_router(getfile_router)
dp.include_router(buy_router)
dp.include_router(page_router)
dp.include_router(account_router)
dp.include_router(withdraw_router)
dp.include_router(help_router)
dp.include_router(about_router)
dp.include_router(admin_router)


# =========================
# FASTAPI APP (WEBHOOK)
# =========================
app = FastAPI()

from handlers.webhook_bayargg import router as webhook_router
app.include_router(webhook_router)

# inject bot ke fastapi
app.state.bot = bot


# =========================
# START BOT
# =========================
async def start_bot():
    await connect_db()
    logging.info("DATABASE CONNECTED")
    logging.info("BOT STARTED")

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types()
    )


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.create_task(start_bot())

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )
