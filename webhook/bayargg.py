@router.post("/bayargg/webhook")
async def webhook(req: Request, x_signature: str = Header(None)):

    bot = req.app.state.bot
    body = await req.body()

    logging.info("📩 Webhook received")

    # VERIFY SIGNATURE
    if not verify_signature(body, x_signature):
        logging.warning("❌ Invalid signature")
        return {"ok": True}

    # PARSE JSON
    try:
        data = json.loads(body.decode())
    except Exception as e:
        logging.error(f"JSON error: {e}")
        return {"ok": True}

    payload = data.get("data") or data

    if payload.get("status") != "PAID":
        return {"ok": True}

    user_id, code = parse_reference(payload.get("reference"))

    if not user_id or not code:
        logging.warning("❌ Invalid reference")
        return {"ok": True}

    pool = await get_pool()

    # LOCK PAYMENT
    updated = await pool.fetchval("""
        UPDATE payments
        SET status='paid'
        WHERE user_id=$1 AND code=$2 AND status='pending'
        RETURNING id
    """, user_id, code)

    if not updated:
        logging.info("⚠️ Payment already processed")
        return {"ok": True}

    # GET FILE + MEDIA
    file = await pool.fetchrow("""
        SELECT seller_id, price, media_json
        FROM files
        WHERE code=$1
    """, code)

    if not file:
        logging.error(f"❌ FILE NOT FOUND: {code}")
        return {"ok": True}

    seller_id = file["seller_id"]
    price = int(file["price"])
    media_json = file["media_json"]

    fee = int(price * 0.10)
    seller_income = price - fee

    # UPDATE BALANCE
    await pool.execute("""
        UPDATE users
        SET balance = COALESCE(balance,0) + $1
        WHERE telegram_id=$2
    """, seller_income, seller_id)

    # TRANSACTION
    await pool.execute("""
        INSERT INTO transactions(user_id, seller_id, code, amount, fee, status)
        VALUES($1,$2,$3,$4,$5,'paid')
        ON CONFLICT DO NOTHING
    """, user_id, seller_id, code, price, fee)

    # GRANT ACCESS
    await pool.execute("""
        INSERT INTO user_access(user_id, code, paid)
        VALUES($1,$2,true)
        ON CONFLICT DO NOTHING
    """, user_id, code)

    logging.info(f"💰 PAID SUCCESS: {user_id} | {code}")

    # =========================
    # SEND FILE
    # =========================
    try:
        media_list = json.loads(media_json)

        await bot.send_message(
            user_id,
            (
                "✅ PAYMENT SUCCESS\n\n"
                f"🔓 Access Granted\n"
                f"📦 Code: {code}\n"
                f"📁 Total File: {len(media_list)}"
            )
        )

        for item in media_list:
            file_id = item.get("file_id")
            media_type = item.get("type")

            if media_type == "document":
                await bot.send_document(user_id, file_id)

            elif media_type == "video":
                await bot.send_video(user_id, file_id)

            elif media_type == "photo":
                await bot.send_photo(user_id, file_id)

    except Exception as e:
        logging.exception(f"SEND FILE ERROR: {e}")

    # =========================
    # NOTIFY GROUP
    # =========================
    try:
        if GROUP_ID:
            await bot.send_message(
                GROUP_ID,
                (
                    "💰 NEW SALE\n"
                    f"📦 {code}\n"
                    f"💸 Rp {price:,}\n"
                    f"👤 {user_id}"
                )
            )
    except Exception as e:
        logging.error(f"GROUP ERROR: {e}")

    return {"ok": True}
