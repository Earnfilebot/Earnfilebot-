import asyncio
from database import get_pool


async def check_payment_loop(bot):
    pool = await get_pool()

    while True:
        try:
            invoices = await pool.fetch(
                "SELECT * FROM invoices WHERE status='pending'"
            )

            for inv in invoices:

                # cek ke gateway (bayar.gg status)
                status = await check_gateway_status(inv["id"])

                if status == "paid":

                    await pool.execute(
                        "UPDATE invoices SET status='paid' WHERE id=$1",
                        inv["id"]
                    )

                    # 🔥 AUTO UNLOCK FILE
                    await pool.execute(
                        """
                        INSERT INTO user_access (user_id, code, paid)
                        VALUES ($1, $2, TRUE)
                        ON CONFLICT DO NOTHING
                        """,
                        inv["user_id"],
                        inv["code"]
                    )

                    # 🔥 NOTIF USER
                    try:
                        await bot.send_message(
                            inv["user_id"],
                            f"✅ PAYMENT SUCCESS\n\n🔓 File `{inv['code']}` sudah terbuka!"
                        )
                    except:
                        pass

        except Exception as e:
            print("CHECK LOOP ERROR:", repr(e))

        await asyncio.sleep(10)
