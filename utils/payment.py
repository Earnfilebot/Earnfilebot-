import httpx
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL


async def create_bayargg_invoice(amount: int, code: str, user_id: int):

    payload = {
        "amount": int(amount),
        "description": f"Purchase file {code}",
        "callback_url": "https://earnfilebot.up.railway.app/webhook/bayargg",
        "external_id": f"{user_id}_{code}"
    }

    headers = {
        "Authorization": f"Bearer {BAYARGG_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        url = f"{BAYARGG_BASE_URL}/transaction/create"

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                url,
                json=payload,
                headers=headers
            )

        # =========================
        # 🔥 DEBUG FULL
        # =========================
        print("===== BAYARGG DEBUG =====")
        print("URL:", url)
        print("STATUS:", r.status_code)
        print("RESPONSE:", r.text)
        print("=========================")

        # =========================
        # ❌ RESPONSE KOSONG
        # =========================
        if not r.text:
            print("❌ RESPONSE KOSONG")
            return None

        # =========================
        # ❌ BUKAN JSON
        # =========================
        try:
            data = r.json()
        except Exception as e:
            print("❌ JSON PARSE ERROR:", e)
            return None

        # =========================
        # ❌ STATUS CODE ERROR
        # =========================
        if r.status_code != 200:
            print("❌ HTTP ERROR:", data)
            return None

        # =========================
        # ❌ FORMAT SALAH
        # =========================
        if not isinstance(data, dict):
            print("❌ FORMAT BUKAN DICT")
            return None

        if "data" not in data:
            print("❌ FIELD 'data' TIDAK ADA:", data)
            return None

        result = data["data"]

        # =========================
        # ❌ FIELD PENTING HILANG
        # =========================
        if not result.get("checkout_url") or not result.get("reference"):
            print("❌ DATA INVOICE TIDAK LENGKAP:", result)
            return None

        # =========================
        # ✅ SUCCESS
        # =========================
        print("✅ INVOICE BERHASIL DIBUAT")
        return result

    except Exception as e:
        print("❌ INVOICE ERROR:", e)
        return None
