import asyncio

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import connect_db

from handlers.check_sub import router as check_sub_router
from handlers.start import router as start_router
from handlers import start, check_sub, upfile

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

dp.include_router(start_router)
dp.include_router(check_sub_router)
dp.include_router(upfile_router)
                  
async def main():
    await connect_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
