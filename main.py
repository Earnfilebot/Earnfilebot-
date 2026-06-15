from fastapi import FastAPI, Request
import json, hmac, hashlib
from database import get_pool
from bot import bot
from utils.crypto import decrypt
from utils.reseller import give_commission

app = FastAPI()

BAYARGG_SECRET = "ISI_SECRET"
