import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

from bot import bot, dp
from database import get_pool, close_db
from webhook.bayargg import router as bayargg_router

logging.basicConfig(level=logging.INFO)


# =========================
# LIFESPAN (STARTUP / SHUTDOWN)
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("🚀 STARTING APP")

    # init DB
    await get_pool()
    logging.info("🔌 DATABASE READY")

    # attach bot ke app state
    app.state.bot = bot
    app.state.dp = dp

    logging.info("🤖 BOT READY")

    yield

    await close_db()
    await bot.session.close()

    logging.info("🛑 STOPPED")


# =========================
# APP
# =========================
app = FastAPI(lifespan=lifespan)

# webhook router
app.include_router(bayargg_router)


# =========================
# HEALTH CHECK
# =========================
@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"ok": True}
