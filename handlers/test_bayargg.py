import httpx

from fastapi import APIRouter

from config import BAYARGG_API_KEY

router = APIRouter()


@router.get("/test-bayargg")
async def test():

    headers = {
        "X-API-Key": BAYARGG_API_KEY
    }

    payload = {
        "amount": 1000,
        "description": "VIP TEST",
        "payment_url": "https://www.bayar.gg/pay"
    }

    async with httpx.AsyncClient(timeout=30) as client:

        r = await client.post(
            "https://www.bayar.gg/api/create-payment.php",
            headers=headers,
            json=payload
        )

    return {
        "status_code": r.status_code,
        "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
    }
