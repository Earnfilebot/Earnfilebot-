from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from bot import bot, dp
from database import get_pool, close_db

app = FastAPI()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("🚀 START APP")

    # Koneksi database
    await get_pool()

    app.state.bot = bot
    app.state.dp = dp

    logging.info("🤖 BOT READY")

    yield

    # Tutup koneksi
    await close_db()
    await bot.session.close()

    logging.info("🛑 APP STOPPED")


app.router.lifespan_context = lifespan


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Decoder File Bot"
    }
