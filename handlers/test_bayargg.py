import logging
import httpx
from fastapi import APIRouter

from config import BAYARGG_API_KEY

router = APIRouter()

@router.get("/test-bayargg")
async def test():

    logging.info("TEST BAYARGG START")

    headers = {
        "X-API-Key": BAYARGG_API_KEY
    }

    payload = {
        "amount": 1000,
        "description": "VIP TEST",
        "payment_url": "https://www.bayar.gg/pay"
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://www.bayar.gg/api/create-payment.php",
                headers=headers,
                json=payload
            )

        logging.info(f"STATUS = {r.status_code}")
        logging.info(r.text)

        return {
            "status": r.status_code,
            "body": r.text
        }

    except Exception as e:
        logging.exception(e)
        return {
            "error": str(e)
        }
