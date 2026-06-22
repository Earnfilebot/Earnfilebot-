from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from bot import bot, dp
from webhook.bayargg import router as bayargg_router
from database import get_pool, close_db

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("🚀 START APP")

    await get_pool()

    app.state.bot = bot
    app.state.dp = dp

    logging.info("🤖 BOT READY")

    yield

    await close_db()
    await bot.session.close()

    logging.info("🛑 STOP")


app = FastAPI(lifespan=lifespan)

# webhook wajib di-load
app.include_router(bayargg_router)


@app.get("/health")
async def health():
    return {"ok": True}
