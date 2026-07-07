from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_pool

router = Router()

LIMIT = 10


# =========================
# LOADING
# =========================
async def loading(call: CallbackQuery):
    try:
        await call.message.edit_text("⏳ Loading...")
    except:
        pass


# =========================
# MASK CODE
# =========================
def mask_code(code: str):

    if len(code) <= 8:
        return "*" * len(code)

    return code[:4] + "****" + code[-2:]


# =========================
# MY CODE
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


    if page < 1:
        page = 1


    offset = (page - 1) * LIMIT


    pool = await get_pool()


    rows = await pool.fetch(
        """
        SELECT
            code,
            price,
            sold_count,
            total_income,
            is_paid

        FROM files

        WHERE
            owner_id=$1
            AND code IS NOT NULL

        ORDER BY
            created_at DESC

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

            price = row["price"] or 0

            sold = row["sold_count"] or 0

            income = row["total_income"] or 0


            text += (
                f"<b>{i + offset}. <code>{code}</code></b>\n"
            )


            if price > 0:

                text += (
                    f"💰 Harga : Rp {price:,}\n"
                    f"🛒 Terjual : {sold}x\n"
                    f"💵 Pendapatan : Rp {income:,}\n\n"
                ).replace(",", ".")


            else:

                text += (
                    "🆓 Gratis\n\n"
                )


    kb = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="⬅️ Prev",
                    callback_data=f"my_code:{max(1,page-1)}"
                ),

                InlineKeyboardButton(
                    text=f"📄 {page}",
                    callback_data="noop"
                ),

                InlineKeyboardButton(
                    text="Next ➡️",
                    callback_data=f"my_code:{page+1}"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🔙 Kembali",
                    callback_data="account"
                )
            ]
        ]
    )


    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb
    )


    await call.answer()



# =========================
# NOOP
# =========================
@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):

    await call.answer()
