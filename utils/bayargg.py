import json
import logging

import httpx

from config import BAYARGG_API_KEY

logger = logging.getLogger(__name__)

BASE_URL = "https://bayar.gg/api"


class BayarGG:

    @staticmethod
    async def create_payment(
        amount: int,
        description: str,
        payment_url: str = "https://bayar.gg/pay",
        callback_url: str | None = None,
        redirect_url: str | None = None,
        customer_name: str | None = None,
        customer_phone: str | None = None,
        payment_method: str = "qris",
    ):

        headers = {
            "X-API-Key": BAYARGG_API_KEY,
            "Content-Type": "application/json"
        }

        payload = {
            "amount": amount,
            "description": description,
            "payment_url": payment_url,
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

        try:
            logger.info("BayarGG create payment request")
            logger.debug(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False
                )
            )

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{BASE_URL}/create-payment.php",
                    headers=headers,
                    json=payload
                )

            logger.info(
                "Create payment status: %s",
                response.status_code
            )

            logger.debug(
                "Create payment body: %s",
                response.text
            )

            response.raise_for_status()

            data = response.json()

            if not data.get("success"):
                raise Exception(
                    data.get("error")
                    or data.get("message")
                    or str(data)
                )

            return data.get("data", data)

        except Exception:
            logger.exception("Create payment failed")
            return None

    @staticmethod
    async def check_payment(invoice_id: str):

        headers = {
            "X-API-Key": BAYARGG_API_KEY
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{BASE_URL}/check-payment.php",
                    headers=headers,
                    params={
                        "invoice": invoice_id
                    }
                )

            logger.info(
                "Check payment status: %s",
                response.status_code
            )

            logger.debug(
                "Check payment body: %s",
                response.text
            )

            response.raise_for_status()

            data = response.json()

            if not data.get("success"):
                raise Exception(
                    data.get("error")
                    or data.get("message")
                    or str(data)
                )

            return data.get("data", data)

        except Exception:
            logger.exception(
                "Check payment failed | invoice=%s",
                invoice_id
            )
            return None
