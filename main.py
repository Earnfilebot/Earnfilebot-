from fastapi import FastAPI
import logging
from contextlib import asynccontextmanager

from bot import bot, dp
from webhook.bayargg import router as bayargg_router
from database import get_pool, close_db

app = FastAPI()

# =========================
# ROUTES
# =========================
app.include_router(bayargg_router)


# =========================
# LIFESPAN
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):

    logging.info("🚀 STARTING APP...")

    await get_pool()

    app.state.bot = bot
    app.state.dp = dp

    logging.info("✅ DATABASE CONNECTED")
    logging.info("🤖 BOT READY (WEBHOOK MODE)")

    yield

    await close_db()
    await bot.session.close()

    logging.info("🛑 BOT STOPPED")


app.router.lifespan_context = lifespan


# =========================
# HEALTH CHECK
# =========================
@app.get("/")
async def root():
    return {"status": "ok", "bot": "running"}
