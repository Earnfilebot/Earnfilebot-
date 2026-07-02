from utils.bayargg import BayarGG
import qrcode
from io import BytesIO

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

from database import get_pool

router = Router()


@router.callback_query(F.data.startswith("pay:"))
async def pay_file(call: CallbackQuery):
    user_id = call.from_user.id
    code = call.data.split(":")[1]

    pool = await get_pool()

    # =========================
    # AMBIL FILE
    # =========================
    file = await pool.fetchrow(
        "SELECT owner_id, price, is_paid FROM files WHERE code=$1",
        code
    )

    if not file:
        return await call.answer("❌ File tidak ditemukan", show_alert=True)

    if not file["is_paid"]:
        return await call.answer("File ini gratis", show_alert=True)

    owner_id = file["owner_id"]
    price = file["price"] or 0

    # =========================
    # OWNER AUTO ACCESS
    # =========================
    if owner_id == user_id:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📂 OPEN PAGE", callback_data=f"page:{code}:1")]
            ]
        )
        await call.message.edit_reply_markup(reply_markup=kb)
        return await call.answer()

    # =========================
    # VIP CHECK
    # =========================
    vip = await pool.fetchval(
        """
        SELECT 1 FROM users
        WHERE telegram_id=$1
        AND vip=TRUE
        AND vip_until > NOW()
        """,
        user_id
    )

    if vip:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📂 OPEN PAGE", callback_data=f"page:{code}:1")]
            ]
        )
        await call.message.edit_reply_markup(reply_markup=kb)
        return await call.answer("💎 VIP aktif", show_alert=True)

    # =========================
    # CEK SUDAH BELI
    # =========================
    purchased = await pool.fetchval(
        """
        SELECT 1 FROM file_purchases
        WHERE user_id=$1 AND file_code=$2 AND status='paid'
        """,
        user_id,
        code
    )

    if purchased:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📂 OPEN PAGE", callback_data=f"page:{code}:1")]
            ]
        )
        await call.message.edit_reply_markup(reply_markup=kb)
        return await call.answer("Sudah dibeli", show_alert=True)

    # =========================
    # CREATE BAYARGG PAYMENT
    # =========================
    try:
        data = await BayarGG.create_payment(
            amount=price,
            description=f"Pembelian File {code}",
            customer_name=call.from_user.full_name
        )

        print("========== DATA ==========")
        print(data)
        print("==========================")

    except Exception as e:
        return await call.answer(
            f"Gagal membuat pembayaran\n{e}",
            show_alert=True
        )

    payment_id = data["payment_id"]
    qr_string = data["qris_string"]

    # =========================
    # CREATE BAYARGG PAYMENT
    # =========================
    try:
        data = await BayarGG.create_payment(
            amount=price,
            description=f"Pembelian File {code}",
            customer_name=call.from_user.full_name
        )

    except Exception as e:
        return await call.answer(
            f"Gagal membuat pembayaran\n{e}",
            show_alert=True
        )

    payment_id = data["payment_id"]
    qr_string = data["qris_string"]

    # =========================
    # SIMPAN PENDING
    # =========================
    await pool.execute(
        """
        INSERT INTO file_purchases
        (user_id, file_code, owner_id, paid_price, status, payment_id)
        VALUES ($1,$2,$3,$4,'pending',$5)
        ON CONFLICT DO NOTHING
        """,
        user_id,
        code,
        owner_id,
        price,
        payment_id
    )

    # =========================
    # GENERATE QR
    # =========================
    qr = qrcode.make(qr_string)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Cek Pembayaran",
                    callback_data=f"checkpay:{payment_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data="cancelpay"
                )
            ]
        ]
    )

    await call.message.answer_photo(
        BufferedInputFile(
            buffer.read(),
            filename="qris.png"
        ),
        caption=(
            "🔒 <b>PEMBAYARAN QRIS</b>\n\n"
            f"💰 Rp {price:,}\n"
            "Scan QR untuk bayar"
        ).replace(",", "."),
        parse_mode="HTML",
        reply_markup=kb
    )

    await call.answer()
