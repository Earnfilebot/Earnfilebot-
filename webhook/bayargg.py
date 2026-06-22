import json
import logging
import asyncio
from fastapi import APIRouter, Request, Header

router = APIRouter()

logging.basicConfig(level=logging.INFO)


@router.api_route("/webhook", methods=["GET", "POST"])
async def webhook(req: Request, x_signature: str = Header(None, alias="X-Signature")):

    body = await req.body()

    logging.info("🔥 ===== WEBHOOK HIT =====")
    logging.info(f"METHOD: {req.method}")
    logging.info(f"SIGNATURE: {x_signature}")
    logging.info(f"BODY RAW: {body.decode(errors='ignore')}")

    try:
        data = json.loads(body.decode()) if body else {}
    except:
        data = {}

    logging.info(f"JSON PARSED: {data}")

    return {
        "ok": True,
        "method": req.method,
        "received": True
    }
