import os
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

from bot import bot, dp
from database import get_pool, close_db
from webhook.bayargg import router as bayargg_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("🚀 STARTING APP")

    await get_pool()

    app.state.bot = bot
    app.state.dp = dp

    logging.info("🤖 READY")

    yield

    await close_db()
    await bot.session.close()


app = FastAPI(lifespan=lifespan)

app.include_router(bayargg_router)


@app.get("/")
async def root():
    return {"ok": True}


@app.get("/health")
async def health():
    return {
        "ok": True,
        "port": os.getenv("PORT")
    }
