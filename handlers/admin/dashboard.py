from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_pool

router = Router()

# =========================
# ADMIN CONFIG
# =========================

ADMIN_IDS = [
    6847035364,
]

def is_admin(user_id: int):
    return user_id in ADMIN_IDS
