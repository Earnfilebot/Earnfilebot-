async def give_commission(pool, user_id, amount):
    reseller = await pool.fetchrow(
        "SELECT parent_id, commission FROM resellers WHERE user_id=$1",
        user_id
    )

    if not reseller or not reseller["parent_id"]:
        return

    profit = int(amount * reseller["commission"] / 100)

    await pool.execute("""
        UPDATE users
        SET balance = balance + $1
        WHERE user_id=$2
    """, profit, reseller["parent_id"])
