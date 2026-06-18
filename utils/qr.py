import qrcode
from io import BytesIO
from aiogram.types import BufferedInputFile


def generate_qr_image(qris_string: str):
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=2
    )
    qr.add_data(qris_string)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return BufferedInputFile(buffer.read(), filename="qris.png")
