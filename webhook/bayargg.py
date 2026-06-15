@app.post("/webhook/bayargg")
async def webhook(req: Request):
    raw = await req.body()
    data = json.loads(raw)

    print("WEBHOOK:", data)

    payload = data.get("data", data)

    reference = payload.get("reference")
    status = payload.get("status")

    if not reference or not status:
        return {"ok": False}

    # =========================
    # ANTI FAKE SIGNATURE
    # =========================
    signature = req.headers.get("X-BAYARGG-SIGNATURE")

    expected = hmac.new(
        BAYARGG_SECRET.encode(),
        raw,
        hashlib.sha256
    ).hexdigest()

    if signature and not hmac.compare_digest(signature, expected):
        print("❌ FAKE WEBHOOK BLOCKED")
        return {"ok": False}

    # =========================
    # PARSE USER
    # =========================
    user_id, code = parse_reference(reference)

    if not user_id:
        return {"ok": False}

    pool = await get_pool()

    # =========================
    # PAID EVENT
    # =========================
    if status.upper() == "PAID":

        # update payment
        await pool.execute("""
            UPDATE payments
            SET status='paid'
            WHERE user_id=$1 AND code=$2
        """, user_id, code)

        # get file
        file = await pool.fetchrow(
            "SELECT * FROM files WHERE code=$1",
            code
        )

        if not file:
            return {"ok": False}

        media = file.get("media") or []
        if isinstance(media, str):
            media = json.loads(media)

        # =========================
        # AUTO UNLOCK (REAL TIME)
        # =========================
        await bot.send_message(
            user_id,
            "✅ PAYMENT SUCCESS\n🔓 FILE UNLOCKED"
        )

        for m in media[:10]:
            try:
                fid = decrypt(m["file_id"])  # 🔐 anti leak
                await bot.send_document(user_id, fid)
            except:
                pass

        # =========================
        # RESELLER PROFIT
        # =========================
        await give_commission(pool, user_id, file["price"])

    return {"ok": True}
