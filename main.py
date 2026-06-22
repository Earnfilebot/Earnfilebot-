app = FastAPI()

app.include_router(bayargg_router)

@app.on_event("startup")
async def startup():
    logging.info("🚀 STARTING APP")
    await get_pool()
    app.state.bot = bot
    app.state.dp = dp
    logging.info("✅ BOT READY")

@app.on_event("shutdown")
async def shutdown():
    await close_db()
    await bot.session.close()
