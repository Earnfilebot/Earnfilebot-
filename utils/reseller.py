async def split_profit_2level(pool, user_id, amount):
    user = await pool.fetchrow("SELECT parent_id, commission FROM users WHERE user_id=$1", user_id)

    if not user:
        return

    parent = user["parent_id"]
    commission = user["commission"] or 0

    if parent and commission > 0:
        bonus = int(amount * commission / 100)

        await pool.execute("""
            UPDATE users SET balance = balance + $1 WHERE user_id=$2
        """, bonus, parent)

        # 🔥 LEVEL 2
        parent2 = await pool.fetchval(
            "SELECT parent_id FROM users WHERE user_id=$1",
            parent
        )

        if parent2:
            bonus2 = int(bonus * 0.3)  # contoh cut 30%

            await pool.execute("""
                UPDATE users SET balance = balance + $1 WHERE user_id=$2
            """, bonus2, parent2)
