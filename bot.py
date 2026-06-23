from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN

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
dp.include_router(help_router)
dp.include_router(about_router)
dp.include_router(admin_router)
