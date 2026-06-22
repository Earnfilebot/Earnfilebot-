from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from bot import bot, dp
from database import get_pool, close_db
from webhook.bayargg import router as bayargg_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("🚀 START APP")

    await get_pool()

    app.state.bot = bot
    app.state.dp = dp

    logging.info("✅ BOT READY")

    yield

    await close_db()
    await bot.session.close()

    logging.info("🛑 STOP")


app = FastAPI(lifespan=lifespan)

# IMPORTANT: webhook harus di-include
app.include_router(bayargg_router)


@app.get("/health")
async def health():
    logging.info("🔥 HEALTH HIT")
    return {"ok": True}


@app.get("/")
async def root():
    return {"status": "ok"}
