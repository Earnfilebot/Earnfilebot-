from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from bot import bot, dp
import webhook.bayargg
from webhook.bayargg import router as bayargg_router
from database import get_pool, close_db


logging.basicConfig(level=logging.INFO)
logging.info("ROUTES LOADED")


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


app = FastAPI(lifespan=lifespan)

app.include_router(bayargg_router)


@app.get("/")
async def root():
    return {"status": "ok"}
