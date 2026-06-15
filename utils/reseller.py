async def split_profit_2level(pool, user_id, amount):
    user = await pool.fetchrow("""
        SELECT parent_id, commission
        FROM users
        WHERE user_id=$1
    """, user_id)

    if not user:
        return

    parent1 = user["parent_id"]
    commission1 = user["commission"] or 0

    # =========================
    # LEVEL 1
    # =========================
    if parent1 and commission1 > 0:
        bonus1 = int(amount * commission1 / 100)

        await pool.execute("""
            UPDATE users
            SET balance = balance + $1
            WHERE user_id=$2
        """, bonus1, parent1)

        # =========================
        # LEVEL 2
        # =========================
        parent2 = await pool.fetchrow("""
            SELECT parent_id, commission
            FROM users
            WHERE user_id=$1
        """, parent1)

        if parent2:
            p2_id = parent2["parent_id"]
            commission2 = parent2["commission"] or 0

            # anti loop / invalid chain
            if p2_id and p2_id != parent1:

                # level 2 pakai commission sendiri (bukan fixed 30%)
                bonus2 = int(amount * commission2 / 100 * 0.5)  # cut 50% dari rate

                if bonus2 > 0:
                    await pool.execute("""
                        UPDATE users
                        SET balance = balance + $1
                        WHERE user_id=$2
                    """, bonus2, p2_id)
