import asyncio

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import connect_db

bot = Bot(BOT_TOKEN)

dp = Dispatcher()

async def main():
    await connect_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
