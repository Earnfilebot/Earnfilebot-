from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from bot import bot, dp
from webhook.bayargg import router as bayargg_router
from database import get_pool, close_db

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("🚀 STARTING APP")

    try:
        await get_pool()
        app.state.bot = bot
        app.state.dp = dp
        logging.info("✅ BOT READY")

    except Exception as e:
        logging.exception(f"❌ STARTUP ERROR: {e}")

    yield

    logging.info("🛑 STOPPING APP")
    await close_db()
    await bot.session.close()


app = FastAPI(lifespan=lifespan)

app.include_router(bayargg_router)


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"ok": True}
