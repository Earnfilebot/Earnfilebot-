import qrcode
from io import BytesIO


def generate_qr_image(data: str):
    try:
        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=2
        )

        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        bio = BytesIO()
        bio.name = "qris.png"
        img.save(bio, "PNG")
        bio.seek(0)

        return bio

    except Exception as e:
        print("QR GENERATE ERROR:", e)
        return None
