from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_pool

router = Router()


# =========================
# PAY FILE
# =========================
@router.callback_query(F.data.startswith("pay:"))
async def pay_file(call: CallbackQuery):

    user_id = call.from_user.id
    code = call.data.split(":")[1]

    pool = await get_pool()

    # =========================
    # Ambil data file
    # =========================
    file = await pool.fetchrow(
        """
        SELECT
            owner_id,
            price,
            is_paid
        FROM files
        WHERE code=$1
        """,
        code
    )

    if not file:
        return await call.answer(
            "❌ File tidak ditemukan",
            show_alert=True
        )

    owner_id = file["owner_id"]
    price = file["price"] or 0

    # =========================
    # FILE GRATIS CHECK
    # =========================
    if not file["is_paid"]:
        return await call.answer(
            "File ini gratis.",
            show_alert=True
        )

    # =========================
    # OWNER AUTO ACCESS
    # =========================
    if owner_id == user_id:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📂 OPEN PAGE",
                        callback_data=f"page:{code}:1"
                    )
                ]
            ]
        )

        await call.message.edit_reply_markup(reply_markup=kb)
        return await call.answer()


    # =========================
    # SUDAH PERNAH BELI?
    # =========================
    purchased = await pool.fetchval(
        """
        SELECT 1
        FROM file_purchases
        WHERE user_id=$1
        AND file_code=$2
        """,
        user_id,
        code
    )

    if purchased:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📂 OPEN PAGE",
                        callback_data=f"page:{code}:1"
                    )
                ]
            ]
        )

        await call.message.edit_reply_markup(reply_markup=kb)

        return await call.answer(
            "✅ Kamu sudah membeli file ini.",
            show_alert=True
        )


    # =========================
    # CEK SALDO
    # =========================
    balance = await pool.fetchval(
        """
        SELECT balance
        FROM users
        WHERE telegram_id=$1
        """,
        user_id
    )

    balance = balance or 0

    if balance < price:
        return await call.answer(
            f"❌ Saldo kurang.\n\nSaldo : Rp {balance:,}\nHarga : Rp {price:,}".replace(",", "."),
            show_alert=True
        )


    # =========================
    # TRANSACTION
    # =========================
    async with pool.acquire() as conn:
        async with conn.transaction():

            await conn.execute(
                """
                UPDATE users
                SET balance = balance - $1
                WHERE telegram_id=$2
                """,
                price,
                user_id
            )

            await conn.execute(
                """
                UPDATE users
                SET
                    balance = balance + $1,
                    total_sales = total_sales + 1
                WHERE telegram_id=$2
                """,
                price,
                owner_id
            )

            await conn.execute(
                """
                UPDATE users
                SET total_downloads = total_downloads + 1
                WHERE telegram_id=$1
                """,
                user_id
            )

            await conn.execute(
                """
                INSERT INTO file_purchases
                (
                    user_id,
                    file_code,
                    owner_id,
                    paid_price
                )
                VALUES
                ($1,$2,$3,$4)
                ON CONFLICT DO NOTHING
                """,
                user_id,
                code,
                owner_id,
                price
            )


    # =========================
    # UNLOCK PAGE
    # =========================
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📂 OPEN PAGE",
                    callback_data=f"page:{code}:1"
                )
            ]
        ]
    )

    await call.message.edit_reply_markup(reply_markup=kb)

    await call.answer(
        "✅ Pembayaran berhasil.",
        show_alert=True
    )
