import httpx
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL


async def create_bayargg_invoice(amount: int, code: str, user_id: int):

    payload = {
        "amount": amount,
        "description": f"Purchase file {code}",
        "callback_url": "https://earnfilebot.up.railway.app/webhook/bayargg",
        "external_id": f"{user_id}_{code}"
    }

    headers = {
        "Authorization": f"Bearer {BAYARGG_API_KEY}"
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BAYARGG_BASE_URL}/transaction/create",
            json=payload,
            headers=headers
        )

    return r.json()
