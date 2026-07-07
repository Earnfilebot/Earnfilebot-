from aiogram import Router
from config import OWNER_ID, ADMINS

router = Router()


# =========================
# CHECK ADMIN
# =========================
def is_admin(user_id: int) -> bool:
    """
    Cek apakah user adalah owner/admin
    """

    admin_list = set()

    # OWNER
    if OWNER_ID:
        try:
            admin_list.add(int(OWNER_ID))
        except:
            pass

    # ADMINS dari env
    if ADMINS:
        for x in ADMINS.split(","):
            x = x.strip()

            if x.isdigit():
                admin_list.add(int(x))

    return user_id in admin_list
