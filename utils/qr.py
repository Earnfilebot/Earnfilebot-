import qrcode
from io import BytesIO
from aiogram.types import BufferedInputFile


def generate_qr_image(qris_string: str):
    qr = qrcode.make(qris_string)

    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)

    return BufferedInputFile(buffer.read(), filename="qris.png")
