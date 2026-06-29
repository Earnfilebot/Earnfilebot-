import httpx

from config import BAYARGG_API_KEY

BASE_URL = "https://www.bayar.gg/api"


class BayarGG:

    @staticmethod
    async def create_payment(
        amount: int,
        description: str,
        callback_url: str = None,
        redirect_url: str = None,
        customer_name: str = None,
        customer_phone: str = None,
        payment_method: str = "qris",
    ):

        headers = {
            "X-API-Key": BAYARGG_API_KEY
        }

        payload = {
            "amount": amount,
            "description": description,
            "payment_url": "https://www.bayar.gg/pay",
            "payment_method": payment_method,
        }

        if callback_url:
            payload["callback_url"] = callback_url

        if redirect_url:
            payload["redirect_url"] = redirect_url

        if customer_name:
            payload["customer_name"] = customer_name

        if customer_phone:
            payload["customer_phone"] = customer_phone

        async with httpx.AsyncClient(timeout=30) as client:

            r = await client.post(
                f"{BASE_URL}/create-payment.php",
                headers=headers,
                json=payload
            )

        r.raise_for_status()

        data = r.json()

        if not data.get("success"):
            raise Exception(data)

        return data["data"]

    @staticmethod
    async def check_payment(invoice_id: str):

        headers = {
            "X-API-Key": BAYARGG_API_KEY
        }

        params = {
            "invoice": invoice_id
        }

        async with httpx.AsyncClient(timeout=30) as client:

            r = await client.get(
                f"{BASE_URL}/check-payment.php",
                headers=headers,
                params=params
            )

        r.raise_for_status()

        return r.json()
