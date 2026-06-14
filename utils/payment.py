import httpx
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL


async def create_bayargg_invoice(amount: int, code: str, user_id: int):

    payload = {
        "amount": int(amount),  # 🔥 pastikan int
        "description": f"Purchase file {code}",
        "callback_url": "https://earnfilebot.up.railway.app/webhook/bayargg",
        "external_id": f"{user_id}_{code}"
    }

    headers = {
        "Authorization": f"Bearer {BAYARGG_API_KEY}"
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{BAYARGG_BASE_URL}/transaction/create",
                json=payload,
                headers=headers
            )

        # 🔥 DEBUG WAJIB
        print("STATUS CODE:", r.status_code)
        print("RESPONSE TEXT:", r.text)

        if r.status_code != 200:
            return None

        data = r.json()

        # 🔥 VALIDASI STRUKTUR
        if "data" not in data:
            print("❌ FORMAT SALAH:", data)
            return None

        return data["data"]

    except Exception as e:
        print("❌ INVOICE ERROR:", e)
        return None
