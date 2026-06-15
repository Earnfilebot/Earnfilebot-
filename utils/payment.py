import httpx
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL


async def create_bayargg_invoice(amount: int, code: str, user_id: int):
    url = f"{BAYARGG_BASE_URL}/create-payment.php"

    payload = {
        "amount": int(amount),
        "description": f"Purchase file {code}",
        "payment_url": "https://www.bayar.gg/pay",
        "payment_method": "qris",
        "external_id": f"{user_id}_{code}"
    }

    headers = {
        "X-API-Key": str(BAYARGG_API_KEY).strip(),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload, headers=headers)

        print("===== BAYARGG DEBUG =====")
        print("URL:", url)
        print("STATUS:", r.status_code)
        print("RESPONSE:", r.text)
        print("=========================")

        if r.status_code != 200:
            return None

        try:
            data = r.json()
        except Exception:
            print("❌ INVALID JSON RESPONSE")
            return None

        if not data.get("success"):
            print("❌ BAYARGG ERROR:", data)
            return None

        result = data.get("data") or {}

        if not isinstance(result, dict):
            print("❌ INVALID RESULT:", result)
            return None

        # =========================
        # 🔥 IMPORTANT FIELDS FIX
        # =========================
        qris_string = result.get("qris_string")

        checkout_url = (
            result.get("payment_url")
            or result.get("checkout_url")
            or result.get("invoice_url")
            or result.get("url")
        )

        invoice_id = result.get("invoice_id")
        reference = f"{user_id}_{code}"

        print("✅ INVOICE SUCCESS")
        print("CHECKOUT:", checkout_url)
        print("QRIS:", bool(qris_string))

        return {
            "invoice_id": invoice_id,
            "qris_string": qris_string,
            "checkout_url": checkout_url,
            "reference": reference,
            "raw": result
        }

    except httpx.ConnectError as e:
        print("❌ CONNECTION ERROR:", e)
        return None

    except httpx.TimeoutException:
        print("❌ TIMEOUT ERROR")
        return None

    except httpx.RequestError as e:
        print("❌ REQUEST ERROR:", e)
        return None

    except Exception as e:
        print("❌ UNKNOWN ERROR:", e)
        return None


# Alias biar aman dengan bot lama
async def create_invoice(amount: int, code: str, user_id: int):
    return await create_bayargg_invoice(amount, code, user_id)
