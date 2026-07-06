import re

from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

router = Router()


@router.message()
async def notify_user(message: Message, state: FSMContext):
    """
    Handler global:
    - Kirim media -> suruh tekan UPFILE
    - Kirim kode/link file -> suruh tekan GETFILE
    - Chat biasa -> balas otomatis
    """

    # Jangan ganggu kalau user sedang di state lain
    current_state = await state.get_state()
    if current_state:
        return

    # =========================
    # USER KIRIM MEDIA
    # =========================
    if (
        message.video
        or message.photo
        or message.document
        or message.audio
        or message.animation
        or message.voice
    ):
        return await message.reply(
            "📤 Untuk mengupload file, silakan tekan tombol UPFILE terlebih dahulu."
        )

    # =========================
    # USER KIRIM TEXT
    # =========================
    if message.text:

        text = message.text.strip()

        # Deteksi kode atau link getfile
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

        # Jika kirim kode file
        if is_getfile_code:
            return await message.reply(
                "📥 Untuk membuka file, silakan tekan tombol GETFILE terlebih dahulu, lalu kirim kode file."
            )

        # =========================
        # CHAT BIASA
        # =========================
        return await message.reply(
            "👋 Halo!\n\n"
            "📤 Jika ingin upload file, tekan tombol UPFILE.\n"
            "📥 Jika ingin membuka file, tekan tombol GETFILE."
        )
