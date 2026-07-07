from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from datetime import datetime, timezone, timedelta

from database import get_pool
from utils.bayargg import BayarGG
from config_vip import VIP_PACKAGES

router = Router()


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
        "Nikmati seluruh fitur premium selama masa VIP aktif.\n\n"

        "✨ <b>Benefit VIP</b>\n"
        "• 🚀 Unlimited Upload\n"
        "• ⚡ Priority Download\n"
        "• 📂 Unlimited Folder\n"
        "• 🎁 Akses File Premium\n"
        "• 🔥 Update Script Tercepat\n"
        "• 💬 Priority Support\n"
        "• 🛡 Tanpa Batas Selama VIP Aktif\n\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "👇 Silakan pilih paket di bawah."
    )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()


@router.callback_query(F.data.startswith("buyvip:"))
async def buy_vip(call: CallbackQuery):

    paket_id = call.data.split(":")[1]

    if paket_id not in VIP_PACKAGES:
        return await call.answer(
            "Paket tidak ditemukan.",
            show_alert=True
        )

    paket = VIP_PACKAGES[paket_id]

    await call.message.edit_text("⏳ Membuat invoice pembayaran...")

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

    invoice_id = payment["invoice_id"]
    payment_url = payment["payment_url"]

    expires_at = datetime.strptime(
        payment["expires_at"],
        "%Y-%m-%d %H:%M:%S"
    ).replace(tzinfo=timezone.utc)

    pool = await get_pool()

    exists = await pool.fetchval(
        """
        SELECT 1
        FROM payments
        WHERE user_id=$1
          AND code=$2
        """,
        call.from_user.id,
        paket_id
    )

    if exists:
        await pool.execute(
            """
            UPDATE payments
            SET
                reference=$3,
                amount=$4,
                status='pending',
                provider='bayargg',
                invoice_id=$5,
                payment_url=$6,
                expires_at=$7,
                updated_at=NOW()
            WHERE user_id=$1
              AND code=$2
            """,
            call.from_user.id,
            paket_id,
            invoice_id,
            paket["price"],
            invoice_id,
            payment_url,
            expires_at
        )
    else:
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
                expires_at
            )
            VALUES
            ($1,$2,$3,$4,'pending','bayargg',$5,$6,$7)
            """,
            call.from_user.id,
            paket_id,
            invoice_id,
            paket["price"],
            invoice_id,
            payment_url,
            expires_at
        )

    kb = InlineKeyboardBuilder()

    kb.button(
        text="💳 Bayar Sekarang",
        url=payment_url
    )

    kb.button(
        text="🔄 Cek Status Pembayaran",
        callback_data=f"cekvip:{invoice_id}"
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
        "Silakan klik tombol <b>Bayar Sekarang</b>.\n"
        "Setelah membayar tekan <b>Cek Status Pembayaran</b>."
    ).replace(",", ".")

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

    await call.answer()


@router.callback_query(F.data.startswith("cekvip:"))
async def check_vip_payment(call: CallbackQuery):

    invoice_id = call.data.split(":")[1]

    await call.answer("⏳ Mengecek pembayaran...")

    try:
        payment = await BayarGG.check_payment(invoice_id)

    except Exception as e:
        return await call.answer(
            f"Gagal cek pembayaran\n{e}",
            show_alert=True
        )

    status = payment.get("status", "").lower()

    # 1. Kalau dari provider belum paid
    if status != "paid":
        return await call.answer(
            f"Status pembayaran: {status.upper()}",
            show_alert=True
        )

    pool = await get_pool()

    trx = await pool.fetchrow(
        """
        SELECT *
        FROM payments
        WHERE invoice_id=$1
        """,
        invoice_id
    )

    if not trx:
        return await call.answer(
            "Invoice tidak ditemukan.",
            show_alert=True
        )

    # 2. Kalau di DB masih belum di-update webhook
    if trx["status"] != "paid":
        return await call.answer(
            "⏳ Pembayaran sudah diterima, sedang memproses aktivasi VIP...\n"
            "Silakan tunggu 3–10 detik lalu cek lagi.",
            show_alert=True
        )

    # 3. Kalau sudah paid & sudah aktif
    await call.message.edit_text(
        (
            "✅ <b>Pembayaran Berhasil</b>\n\n"
            "VIP sudah berhasil diaktifkan.\n"
            "Silakan kembali ke menu akun."
        ),
        parse_mode="HTML"
    )

    await call.answer()
