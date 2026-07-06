from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from middlewares.ban import BanMiddleware

# =========================
# BOT INIT
# =========================
bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)

dp = Dispatcher()

dp.message.middleware(BanMiddleware())
dp.callback_query.middleware(BanMiddleware())

# =========================
# ROUTERS IMPORT
# =========================

from handlers.start import router as start_router
from handlers.check_sub import router as check_sub_router
from handlers.upfile import router as upfile_router
from handlers.getfile import router as getfile_router
from handlers.page import router as page_router
from handlers.pay import router as pay_router
from handlers.account import router as account_router
from handlers.my_code import router as my_code_router
from handlers.vvip import router as vvip_router
from handlers.help import router as help_router
from handlers.about import router as about_router
from handlers.admin import router as admin_router
from handlers.notify import router as notify_router

# =========================
# REGISTER ROUTERS
# =========================

dp.include_router(start_router)
dp.include_router(check_sub_router)
dp.include_router(upfile_router)
dp.include_router(getfile_router)
dp.include_router(page_router)
dp.include_router(pay_router)
dp.include_router(account_router)
dp.include_router(my_code_router)
dp.include_router(vvip_router)
dp.include_router(help_router)
dp.include_router(about_router)
dp.include_router(admin_router)
dp.include_router(notify_router)
