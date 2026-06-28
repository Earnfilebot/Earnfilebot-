import asyncio
import logging

async def payment_worker():
    logging.info("💳 Payment worker running...")

    while True:
        try:
            # TODO: cek status pembayaran BayarGG
            await asyncio.sleep(10)
        except Exception as e:
            logging.exception(e)
            await asyncio.sleep(5)
