import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from bot import bot, dp
from database import get_pool, close_db

polling_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global polling_task

    logging.info("🚀 START APP")

    # Database
    await get_pool()

    # Hapus webhook lama
    await bot.delete_webhook(drop_pending_updates=True)

    # Cek login bot
    me = await bot.get_me()
    logging.info(f"🤖 Login sebagai @{me.username}")

    # Jalankan polling
    polling_task = asyncio.create_task(
        dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    )

    logging.info("✅ BOT POLLING STARTED")

    yield

    logging.info("🛑 STOPPING...")

    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass

    await close_db()
    await bot.session.close()

    logging.info("✅ APP STOPPED")


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"status": "running"}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Decoder File Bot",
    }
