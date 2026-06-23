import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from bot import bot, dp
from database import get_pool, close_db
from tasks.auto_delete import auto_delete_worker

polling_task = None
auto_delete_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):

    global polling_task, auto_delete_task

    logging.info("🚀 START APP")

    # =========================
    # DATABASE INIT
    # =========================
    await get_pool()

    # =========================
    # CLEAN OLD WEBHOOK
    # =========================
    await bot.delete_webhook(drop_pending_updates=True)

    # =========================
    # BOT INFO CHECK
    # =========================
    me = await bot.get_me()
    logging.info(f"🤖 Login sebagai @{me.username}")

    # =========================
    # START AUTO DELETE WORKER
    # =========================
    auto_delete_task = asyncio.create_task(auto_delete_worker())
    logging.info("🧹 AUTO DELETE WORKER STARTED")

    # =========================
    # START POLLING
    # =========================
    polling_task = asyncio.create_task(
        dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    )

    logging.info("✅ BOT POLLING STARTED")

    yield

    # =========================
    # SHUTDOWN
    # =========================
    logging.info("🛑 STOPPING...")

    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass

    if auto_delete_task:
        auto_delete_task.cancel()
        try:
            await auto_delete_task
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
