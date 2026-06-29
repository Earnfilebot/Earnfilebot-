import httpx
import json

from config import BAYARGG_API_KEY

BASE_URL = "https://www.bayar.gg/api"


class BayarGG:

    @staticmethod
    async def create_payment(
        amount: int,
        description: str,
        callback_url: str | None = None,
        redirect_url: str | None = None,
        customer_name: str | None = None,
        customer_phone: str | None = None,
        payment_method: str = "qris",
    ):

        headers = {
            "X-API-Key": BAYARGG_API_KEY
        }

        payload = {
            "amount": amount,
            "description": description,
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
            response = await client.post(
                f"{BASE_URL}/create-payment.php",
                headers=headers,
                json=payload
            )

        response.raise_for_status()

        data = response.json()

        print("========== BAYARGG RESPONSE ==========")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("=====================================")

        if not data.get("success"):
            raise Exception(
                data.get("message", str(data))
            )

        result = data.get("data", {})

        result["payment_url"] = data.get(
            "payment_url",
            result.get("payment_url")
        )

        result["qris_string"] = data.get(
            "qris_string",
            result.get("qris_string")
        )

        return result

    @staticmethod
    async def check_payment(invoice_id: str):

        headers = {
            "X-API-Key": BAYARGG_API_KEY
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{BASE_URL}/check-payment.php",
                headers=headers,
                params={
                    "invoice": invoice_id
                }
            )

        response.raise_for_status()

        data = response.json()

        if not data.get("success"):
            raise Exception(
                data.get("message", str(data))
            )

        return data
