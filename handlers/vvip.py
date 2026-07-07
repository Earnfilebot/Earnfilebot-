import qrcode
from io import BytesIO

from aiogram.types import BufferedInputFile
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from datetime import datetime

from database import get_pool
from utils.bayargg import BayarGG
from config_vip import VIP_PACKAGES


router = Router()


# =========================
# VIP MENU
# =========================
@router.callback_query(F.data == "vvip")
async def vvip_menu(call: CallbackQuery):

    kb = InlineKeyboardBuilder()

    for key, paket in VIP_PACKAGES.items():

        kb.button(
            text=f"💎 {paket['name']} • Rp {paket['price']:,}".replace(",", "."),
            callback_data=f"buyvip:{key}"
        )

    kb.button(
        text="🔙 Kembali",
        callback_data="account"
    )

    kb.adjust(1)


    text = (
        "💎 <b>VVIP PREMIUM ACCESS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        "Nikmati seluruh fitur premium selama VIP aktif.\n\n"

        "✨ <b>Benefit VIP</b>\n"
        "• 🚀 Unlimited Upload\n"
        "• ⚡ Priority Download\n"
        "• 📂 Unlimited Folder\n"
        "• 🎁 Akses File Premium\n"
        "• 🔥 Update Script Tercepat\n"
        "• 💬 Priority Support\n"
        "• 🛡 VIP Aktif Sesuai Durasi Paket\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "👇 Pilih paket VIP:"
    )


    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()



# =========================
# BUY VIP
# =========================
@router.callback_query(F.data.startswith("buyvip:"))
async def buy_vip(call: CallbackQuery):

    paket_id = call.data.split(":")[1]


    if paket_id not in VIP_PACKAGES:

        return await call.answer(
            "Paket tidak ditemukan.",
            show_alert=True
        )


    paket = VIP_PACKAGES[paket_id]


    await call.message.edit_text(
        "⏳ Membuat invoice pembayaran..."
    )


    try:

        payment = await BayarGG.create_payment(
            amount=paket["price"],
            description=paket["name"],
            payment_url="https://www.bayar.gg/pay",
            callback_url="https://earnfilebot-production.up.railway.app/bayargg/webhook",
            customer_name=call.from_user.full_name,
            payment_method="qris"
        )


    except Exception as e:

        return await call.message.edit_text(
            f"❌ Gagal membuat invoice.\n\n<code>{e}</code>",
            parse_mode="HTML"
        )

    if not payment:
        return await call.message.edit_text(
            "❌ Gagal membuat invoice pembayaran.\nSilakan coba lagi."
        )


    invoice_id = payment["invoice_id"]

    payment_url = payment["payment_url"]

    qr_string = payment["qris_string"]


    try:
        expires_at = datetime.fromisoformat(
            payment.get("expires_at")
        )
    except Exception:
        expires_at = None


    pool = await get_pool()


    # =========================
    # SIMPAN TRANSAKSI VIP
    # =========================

    try:
        await pool.execute(
            """
            INSERT INTO payments
            (
                user_id,
                code,
                reference,
                amount,
                status,
                provider,
                invoice_id,
                payment_url,
                expires_at,
                type
            )
            VALUES
            (
                $1,
                $2,
                $3,
                $4,
                'pending',
                'bayargg',
                $5,
                $6,
                $7,
                'vip'
            )
            """,

            call.from_user.id,
            paket_id,
            invoice_id,
            paket["price"],
            invoice_id,
            payment_url,
            expires_at
        )

    except Exception as e:

        return await call.message.edit_text(
            f"❌ Gagal menyimpan transaksi.\n\n<code>{e}</code>",
            parse_mode="HTML"
        )


    kb = InlineKeyboardBuilder()


    kb.button(
        text="✅ Check Payment",
        callback_data=f"checkvip:{invoice_id}"
    )


    kb.button(
        text="🔙 Kembali",
        callback_data="vvip"
    )


    kb.adjust(1)


    text = (
        "💎 <b>INVOICE VIP BERHASIL DIBUAT</b>\n"
        "━━━━━━━━━━━━━━\n\n"

        f"📦 Paket : <b>{paket['name']}</b>\n"
        f"💰 Harga : <b>Rp {paket['price']:,}</b>\n"
        f"🧾 Invoice :\n<code>{invoice_id}</code>\n\n"

        "⏳ Status : <b>MENUNGGU PEMBAYARAN</b>\n\n"

        "Scan QRIS di bawah untuk melakukan pembayaran.\n"
        "VIP akan aktif otomatis setelah pembayaran berhasil."
    ).replace(",", ".")


    # =========================
    # GENERATE QR
    # =========================

    qr = qrcode.make(
        qr_string
    )

    buf = BytesIO()

    qr.save(
        buf,
        format="PNG"
    )

    buf.seek(0)


    # =========================
    # SEND QR
    # =========================

    await call.message.answer_photo(
        BufferedInputFile(
            buf.getvalue(),
            filename="vip_qris.png"
        ),
        caption=text,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


    await call.answer()
