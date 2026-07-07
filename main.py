import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import TIMEZONE
from bot import bot, dp
from database import get_pool, close_db

# routers
from handlers.bayargg import router as bayargg_router

# workers
from tasks.auto_delete import auto_delete_worker
from tasks.payment_worker import payment_worker


# =========================
# TIMEZONE
# =========================
os.environ["TZ"] = TIMEZONE
if hasattr(time, "tzset"):
    time.tzset()

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# =========================
# GLOBAL TASKS
# =========================
tasks = {}


# =========================
# SAFE CREATE TASK
# =========================
def create_task(name, coro):
    if name in tasks and not tasks[name].done():
        logging.warning(f"⚠️ {name} already running")
        return

    task = asyncio.create_task(coro)
    tasks[name] = task
    logging.info(f"✅ {name} started")


# =========================
# SAFE STOP TASK
# =========================
async def stop_task(name):
    task = tasks.get(name)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logging.info(f"❌ {name} stopped")


# =========================
# START WORKERS
# =========================
async def start_workers():
    create_task("AUTO_DELETE", auto_delete_worker())
    create_task("PAYMENT", payment_worker())
    create_task("SCHEDULER", scheduler_loop(bot))

    # polling bot
    create_task(
        "POLLING",
        dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    )


# =========================
# FASTAPI LIFESPAN
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("🚀 APP STARTING...")

    # init DB
    await get_pool()

    # reset webhook
    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    logging.info(f"🤖 Logged in as @{me.username}")

    # start all workers
    await start_workers()

    yield

    # =========================
    # SHUTDOWN
    # =========================
    logging.info("🛑 SHUTDOWN...")

    for name in list(tasks.keys()):
        await stop_task(name)

    await close_db()
    await bot.session.close()

    logging.info("✅ APP STOPPED")


# =========================
# APP INIT
# =========================
app = FastAPI(lifespan=lifespan)

app.include_router(bayargg_router)


# =========================
# ROUTES
# =========================
@app.get("/")
async def root():
    return {"status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
