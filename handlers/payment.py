from utils.qr import generate_qr_image

@router.callback_query(F.data.startswith("buy:"))
async def buy(call: CallbackQuery):
    code = call.data.split(":")[1]
    user_id = call.from_user.id

    pool = await get_pool()

    file = await pool.fetchrow(
        "SELECT price FROM files WHERE code=$1",
        code
    )

    price = int(file["price"])

    result = await create_bayargg_invoice(price, code, user_id)

    if not result:
        return await call.answer("❌ invoice gagal", show_alert=True)

    qris = result.get("qris_string")
    checkout = result.get("checkout_url")

    # =========================
    # QRIS IMAGE MODE (FIX)
    # =========================
    if qris:
        qr_img = generate_qr_image(qris)

        await call.message.answer_photo(
            qr_img,
            caption=(
                "💳 INVOICE CREATED\n\n"
                f"📦 CODE: {code}\n"
                f"💰 PRICE: {price}\n\n"
                "🔽 Scan QR di bawah"
            )
        )
    else:
        await call.message.answer(f"🔗 PAY LINK:\n{checkout}")

    await call.answer()
