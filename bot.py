import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from fastapi import FastAPI
import uvicorn

from config import BOT_TOKEN
from database import get_pool, close_db

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
# ROUTERS
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
# WEBHOOK ROUTER
# =========================
from webhook import bayargg as webhook_handler

# =========================
# POLLING TASK
# =========================
async def start_polling():
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types()
    )

# =========================
# FASTAPI LIFESPAN (FIX MODERN)
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # =========================
    # STARTUP
    # =========================
    await get_pool()
    logging.info("DATABASE CONNECTED")

    await bot.delete_webhook(drop_pending_updates=True)

    polling_task = asyncio.create_task(start_polling())
    logging.info("BOT STARTED")

    yield  # server running

    # =========================
    # SHUTDOWN
    # =========================
    polling_task.cancel()
    await close_db()
    await bot.session.close()
    logging.info("BOT STOPPED")

# =========================
# FASTAPI APP
# =========================
app = FastAPI(lifespan=lifespan)

app.include_router(webhook_handler.router)
app.state.bot = bot

# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )
