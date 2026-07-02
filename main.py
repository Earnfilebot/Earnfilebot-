import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from handlers.bayargg import router as bayargg_router
from tasks.payment_worker import payment_worker

from config import TIMEZONE
from bot import bot, dp
from database import get_pool, close_db
from tasks.auto_delete import auto_delete_worker

os.environ["TZ"] = TIMEZONE
if hasattr(time, "tzset"):
    time.tzset()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

polling_task = None
auto_delete_task = None
payment_task = None


# =========================
# WORKERS
# =========================
async def start_workers():
    global auto_delete_task, payment_task, polling_task

    auto_delete_task = asyncio.create_task(auto_delete_worker())
    logging.info("🧹 AUTO DELETE WORKER STARTED")

    payment_task = asyncio.create_task(payment_worker())
    logging.info("💳 PAYMENT WORKER STARTED")

    polling_task = asyncio.create_task(
        dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    )
    logging.info("🤖 BOT POLLING STARTED")


# =========================
# FASTAPI LIFESPAN
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):

    logging.info("🚀 START APP")

    await get_pool()

    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    logging.info(f"🤖 Login sebagai @{me.username}")

    await start_workers()

    yield

    logging.info("🛑 STOPPING...")

    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except:
            pass

    if auto_delete_task:
        auto_delete_task.cancel()
        try:
            await auto_delete_task
        except:
            pass

    if payment_task:
        payment_task.cancel()
        try:
            await payment_task
        except:
            pass

    await close_db()
    await bot.session.close()

    logging.info("✅ APP STOPPED")


app = FastAPI(lifespan=lifespan)

app.include_router(bayargg_router)


@app.get("/")
async def root():
    return {"status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
