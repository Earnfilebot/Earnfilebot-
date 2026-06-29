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
        "<b>📦 Daftar Paket VIP</b>\n\n"

        "💎 VIP 1 Hari  — Rp15.000\n"
        "💎 VIP 3 Hari  — Rp25.000\n"
        "💎 VIP 5 Hari  — Rp35.000\n"
        "💎 VIP 7 Hari  — Rp45.000\n"
        "💎 VIP 10 Hari — Rp50.000\n"
        "💎 VIP 20 Hari — Rp70.000\n"
        "💎 VIP 30 Hari — Rp100.000\n\n"

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
        ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        """,
        call.from_user.id,
        paket_id,
        invoice_id,
        paket["price"],
        "pending",
        "bayargg",
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

    if trx["status"] == "paid":
        return await call.answer(
            "VIP sudah aktif.",
            show_alert=True
        )

    await pool.execute(
        """
        UPDATE payments
        SET
            status='paid',
            updated_at=NOW()
        WHERE invoice_id=$1
        """,
        invoice_id
    )

    paket = VIP_PACKAGES[trx["code"]]

    user = await pool.fetchrow(
        """
        SELECT vip_until
        FROM users
        WHERE telegram_id=$1
        """,
        call.from_user.id
    )

    now = datetime.now(timezone.utc)

    if (
        user
        and user["vip_until"]
        and user["vip_until"] > now
    ):
        vip_until = user["vip_until"] + timedelta(days=paket["days"])
    else:
        vip_until = now + timedelta(days=paket["days"])

    await pool.execute(
        """
        UPDATE users
        SET
            vip=TRUE,
            is_vip=TRUE,
            vip_until=$1
        WHERE telegram_id=$2
        """,
        vip_until,
        call.from_user.id
    )

    await pool.execute(
        """
        INSERT INTO vip_users
        (
            user_id,
            plan,
            invoice_id,
            started_at,
            expires_at,
            active
        )
        VALUES
        ($1,$2,$3,NOW(),$4,TRUE)
        """,
        call.from_user.id,
        paket["name"],
        invoice_id,
        vip_until
    )

    await call.message.edit_text(
        (
            "✅ <b>Pembayaran Berhasil</b>\n\n"
            f"💎 Paket : <b>{paket['name']}</b>\n"
            f"📅 VIP Aktif Sampai:\n"
            f"<code>{vip_until.strftime('%d-%m-%Y %H:%M:%S UTC')}</code>\n\n"
            "Terima kasih telah membeli VIP ❤️"
        ),
        parse_mode="HTML"
    )

    await call.answer()
