import re

from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

router = Router()


@router.message()
async def notify_user(message: Message, state: FSMContext):
    """
    Handler global:
    - Kirim media -> arahkan ke UPFILE
    - Kirim kode/link -> arahkan ke GETFILE
    - Chat biasa -> arahkan ke HELP
    """

    # Jangan ganggu jika user sedang menggunakan fitur lain
    current_state = await state.get_state()
    if current_state:
        return

    # =====================================
    # USER MENGIRIM MEDIA
    # =====================================
    if (
        message.video
        or message.photo
        or message.document
        or message.audio
        or message.animation
        or message.voice
    ):
        return await message.reply(
            "📤 <b>Upload File</b>\n\n"
            "Untuk mengupload file, silakan tekan tombol <b>UPFILE</b> terlebih dahulu.\n\n"
            "❓ Jika masih bingung cara menggunakannya, silakan buka menu <b>HELP / BANTUAN</b> untuk melihat panduan lengkap."
        )

    # =====================================
    # USER MENGIRIM TEXT
    # =====================================
    if message.text:

        text = message.text.strip()

        is_getfile_code = False

        if "getfile_" in text.lower():
            is_getfile_code = True

        elif re.search(
            r"code\s*[:：]\s*[A-Za-z0-9_-]+",
            text,
            re.IGNORECASE
        ):
            is_getfile_code = True

        elif re.search(
            r"DecoderFileBot[A-Za-z0-9_-]+",
            text
        ):
            is_getfile_code = True

        # =====================================
        # USER MENGIRIM KODE FILE
        # =====================================
        if is_getfile_code:
            return await message.reply(
                "📥 <b>Get File</b>\n\n"
                "Untuk membuka file, silakan tekan tombol <b>GETFILE</b> terlebih dahulu, kemudian kirim kode file tersebut.\n\n"
                "❓ Jika masih bingung, silakan buka menu <b>HELP / BANTUAN</b> untuk melihat panduan lengkap."
            )

        # =====================================
        # CHAT BIASA
        # =====================================
        return await message.reply(
            "👋 Halo!\n\n"
            "Silakan pilih menu sesuai kebutuhan:\n\n"
            "📤 <b>UPFILE</b>\n"
            "Untuk upload file dan menghasilkan uang.\n\n"
            "📥 <b>GETFILE</b>\n"
            "Untuk membuka file menggunakan kode.\n\n"
            "❓ <b>HELP / BANTUAN</b>\n"
            "Berisi panduan lengkap mulai dari:\n"
            "• Cara Upload File\n"
            "• Cara Get File\n"
            "• Cara Mendapatkan Cuan\n"
            "• Cara Withdraw\n"
            "• Informasi VVIP"
        )
