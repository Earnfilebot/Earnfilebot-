from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from states import WithdrawState
from database import fetchrow, transaction
from config import GROUP_ID  # opsional (buat notif admin)

router = Router()


# =========================
# 📌 MENU WITHDRAW
# =========================
@router.callback_query(F.data == "withdraw")
async def withdraw_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(WithdrawState.amount)

    await call.message.edit_text(
        "💸 <b>WITHDRAW</b>\n\n"
        "Masukkan jumlah withdraw:\n"
        "Contoh: 50000"
    )

    await call.answer()


# =========================
# 📌 PROSES INPUT NOMINAL
# =========================
@router.message(WithdrawState.amount)
async def process_withdraw(message: Message, state: FSMContext):

    # =========================
    # VALIDASI ANGKA
    # =========================
    try:
        amount = int(message.text)
    except:
        return await message.reply("❌ Masukkan angka yang valid")

    if amount <= 0:
        return await message.reply("❌ Nominal tidak valid")

    if amount < 10000:
        return await message.reply("❌ Minimal withdraw Rp 10.000")

    user_id = message.from_user.id

    # =========================
    # CEK SALDO
    # =========================
    user = await fetchrow(
        "SELECT balance FROM users WHERE telegram_id=$1",
        user_id
    )

    if not user:
        return await message.reply("❌ User tidak ditemukan")

    if user["balance"] < amount:
        return await message.reply("❌ Saldo tidak cukup")

    # =========================
    # ANTI DOUBLE WITHDRAW
    # =========================
    pending = await fetchrow(
        "SELECT id FROM withdraw_requests WHERE user_id=$1 AND status='pending'",
        user_id
    )

    if pending:
        return await message.reply("❌ Masih ada withdraw yang pending")

    # =========================
    # TRANSACTION (AMAN)
    # =========================
    try:
        await transaction([
            (
                "UPDATE users SET balance = balance - $1 WHERE telegram_id=$2",
                amount, user_id
            ),
            (
                "INSERT INTO withdraw_requests(user_id, amount) VALUES($1,$2)",
                user_id, amount
            )
        ])
    except Exception as e:
        return await message.reply("❌ Terjadi kesalahan, coba lagi")

    await state.clear()

    # =========================
    # RESPON KE USER
    # =========================
    await message.answer(
        "✅ <b>Withdraw berhasil diajukan</b>\n\n"
        f"💸 Jumlah: Rp {amount:,}\n"
        "⏳ Status: Pending"
    )

    # =========================
    # NOTIF ADMIN (OPSIONAL)
    # =========================
    try:
        await message.bot.send_message(
            GROUP_ID,
            "💸 <b>REQUEST WITHDRAW</b>\n\n"
            f"👤 User: <code>{user_id}</code>\n"
            f"💰 Jumlah: Rp {amount:,}\n"
            "📌 Status: Pending"
        )
    except:
        pass
