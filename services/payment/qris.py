from io import BytesIO

import qrcode
from aiogram.types import BufferedInputFile


class QRISService:

    @staticmethod
    def generate(qris_string: str) -> BufferedInputFile:

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4
        )

        qr.add_data(qris_string)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return BufferedInputFile(
            buffer.getvalue(),
            filename="qris.png"
        )
