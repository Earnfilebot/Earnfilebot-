import json
import logging
from database import get_pool


async def process_payment(ref: str, status: str, bot):
    pool = await get_pool()

    payment = await pool.fetchrow("""
        SELECT user_id, code
        FROM payments
        WHERE invoice_id=$1 OR external_id=$1 OR code=$1
    """, ref)

    if not payment:
        logging.warning("❌ PAYMENT NOT FOUND")
        return False

    user_id = payment["user_id"]
    code = payment["code"]

    # update payment
    await pool.execute("""
        UPDATE payments
        SET status='paid'
        WHERE user_id=$1 AND code=$2 AND status='pending'
    """, user_id, code)

    # access grant
    await pool.execute("""
        INSERT INTO user_access(user_id, code, paid)
        VALUES ($1,$2,TRUE)
        ON CONFLICT (user_id, code)
        DO UPDATE SET paid=TRUE
    """, user_id, code)

    # ambil file
    file = await pool.fetchrow("""
        SELECT seller_id, price, media_json
        FROM files
        WHERE code=$1
    """, code)

    if not file:
        return False

    seller_id = file["seller_id"]
    price = int(file["price"] or 0)

    try:
        media = json.loads(file["media_json"] or "[]")
    except:
        media = []

    fee = int(price * 0.1)
    income = price - fee

    await pool.execute("""
        INSERT INTO users (telegram_id, balance)
        VALUES ($1,$2)
        ON CONFLICT (telegram_id)
        DO UPDATE SET balance = users.balance + EXCLUDED.balance
    """, seller_id, income)

    # notify buyer
    await bot.send_message(
        user_id,
        f"""✅ PAYMENT SUCCESS
CODE: {code}
FILES: {len(media)}"""
    )

    # send files
    for item in media:
        try:
            fid = item.get("file_id")
            t = item.get("type")

            if t == "video":
                await bot.send_video(user_id, fid)
            elif t == "document":
                await bot.send_document(user_id, fid)
            else:
                await bot.send_photo(user_id, fid)

        except:
            pass

    logging.info(f"✅ PAYMENT DONE {user_id} {code}")

    return True
