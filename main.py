from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from bot import bot, dp
from webhook.bayargg import router as bayargg_router
from database import get_pool, close_db

app = FastAPI()
app.include_router(bayargg_router)

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):

    logging.info("🚀 STARTING APP")

    await get_pool()

    app.state.bot = bot
    app.state.dp = dp

    logging.info("✅ BOT READY")

    yield

    await close_db()
    await bot.session.close()

    logging.info("🛑 STOPPED")

app.router.lifespan_context = lifespan


@app.get("/")
async def root():
    return {"status": "ok"}
