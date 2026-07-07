from aiogram import Router

router = Router()

# =========================
# ADMIN LIST
# =========================
ADMINS = [
    6847035364  # 🔥 GANTI DENGAN USER ID TELEGRAM KAMU
]

# =========================
# CHECK ADMIN
# =========================
def is_admin(user_id: int) -> bool:
    return user_id in ADMINS
