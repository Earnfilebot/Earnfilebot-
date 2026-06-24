from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_pool

router = Router()

# =========================
# CONFIG
# =========================
LIMIT = 10  # ubah ke 20 kalau mau
MAX_SHOW = 6  # anti leak (potong tampilan code)


# =========================
# LOADING
# =========================
async def loading(call: CallbackQuery):
    await call.message.edit_text("⏳ Loading...")


# =========================
# MASK CODE (ANTI LEAK)
# =========================
def mask_code(code: str):
    if len(code) <= 8:
        return "*" * len(code)

    return code[:4] + "****" + code[-2:]


# =========================
# MY CODE (PAGINATION)
# =========================
@router.callback_query(F.data.startswith("my_code"))
async def my_code(call: CallbackQuery):

    await loading(call)

    page = 1
    parts = call.data.split(":")
    if len(parts) > 1:
        try:
            page = int(parts[1])
        except:
            page = 1

    offset = (page - 1) * LIMIT

    pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT code
        FROM transactions
        WHERE user_id = $1
        AND code IS NOT NULL
        ORDER BY id DESC
        LIMIT $2 OFFSET $3
        """,
        call.from_user.id,
        LIMIT,
        offset
    )

    text = (
        "📦 <b>MY CODE</b>\n"
        "━━━━━━━━━━━━━━\n\n"
    )

    if not rows:
        text += "❌ Belum ada code."
    else:
        for i, row in enumerate(rows, start=1):
            code = mask_code(row["code"])
            text += f"{i + offset}. <code>{code}</code>\n"

    # =========================
    # PAGINATION BUTTON
    # =========================
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Prev",
                    callback_data=f"my_code:{page-1 if page > 1 else 1}"
                ),
                InlineKeyboardButton(
                    text=f"📄 {page}",
                    callback_data="noop"
                ),
                InlineKeyboardButton(
                    text="Next ➡️",
                    callback_data=f"my_code:{page+1}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Kembali",
                    callback_data="account"
                )
            ]
        ]
    )

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# =========================
# NOOP (biar tombol page tidak error)
# =========================
@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()
