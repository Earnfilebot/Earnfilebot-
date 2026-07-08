import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

HELP_CACHE = {}


def get_cache(key):
    return HELP_CACHE.get(key)


def set_cache(key, value):
    HELP_CACHE[key] = value


async def loading(call: CallbackQuery):
    try:
        await call.message.edit_text("⏳ Loading...")
    except:
        pass

    await asyncio.sleep(0.3)


def kb_builder(buttons):
    builder = InlineKeyboardBuilder()

    for text, data in buttons:
        builder.button(text=text, callback_data=data)

    builder.adjust(1)
    return builder.as_markup()


# =====================================
# HELP MENU
# =====================================
@router.callback_query(F.data == "help")
async def help_menu(call: CallbackQuery):

    await loading(call)

    text = (
        "━━━━━━━━━━━━━━\n"
        "❓ <b>HELP CENTER</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "Selamat datang di pusat bantuan.\n\n"
        "Silakan pilih panduan yang ingin dipelajari.\n\n"
        "Semua tutorial dibuat agar pengguna baru bisa langsung memahami cara menggunakan bot dari awal sampai menghasilkan penghasilan."
    )

    kb = kb_builder([
        ("📤 Cara Upload File", "help_upfile"),
        ("📥 Cara Get File", "help_getfile"),
        ("💰 Cara Mendapatkan Cuan", "help_money"),
        ("🏦 Cara Withdraw", "help_withdraw"),
        ("💎 VVIP", "help_vvip"),
        ("🏠 Home", "home"),
    ])

    await call.message.edit_text(
        text,
        reply_markup=kb
    )

    await call.answer()


# =====================================
# TEMPLATE
# =====================================
async def help_template(call, key, content):

    cache = get_cache(key)

    if cache is None:
        set_cache(key, content)
        cache = content

    await loading(call)

    kb = kb_builder([
        ("🔙 Kembali", "help")
    ])

    await call.message.edit_text(
        cache,
        reply_markup=kb
    )

    await call.answer()


# =====================================
# UPFILE
# =====================================
@router.callback_query(F.data == "help_upfile")
async def help_upfile(call: CallbackQuery):

    await help_template(
        call,
        "upfile",
        """━━━━━━━━━━━━━━
📤 <b>CARA UPLOAD FILE</b>
━━━━━━━━━━━━━━

1️⃣ Masuk ke menu <b>UP FILE</b>

2️⃣ Kirim file yang ingin dijual.
Bot mendukung:
• Foto
• Video
• Dokumen
• ZIP
• RAR
• APK
• PDF
• Dan file lainnya.

3️⃣ Setelah semua file selesai dikirim,
tekan tombol <b>SELESAI / DONE</b>.

4️⃣ Masukkan harga file.

Contoh:
1000
5000
10000
25000
50000

Semakin menarik isi file,
semakin tinggi harga yang bisa dipasang.

5️⃣ Bot akan membuat CODE secara otomatis.

Contoh:
ABC123XYZ

6️⃣ Bagikan CODE tersebut kepada orang lain.

Jika seseorang membeli atau membuka file berbayar tersebut,
saldo Anda akan otomatis bertambah ke akun bot.

━━━━━━━━━━━━━━
Tips:

✔ Gunakan judul yang menarik.

✔ Upload file berkualitas.

✔ Promosikan kode Anda agar lebih banyak pembeli.
"""
    )


# =====================================
# GET FILE
# =====================================
@router.callback_query(F.data == "help_getfile")
async def help_getfile(call: CallbackQuery):

    await help_template(
        call,
        "getfile",
        """━━━━━━━━━━━━━━
📥 <b>CARA GET FILE</b>
━━━━━━━━━━━━━━

1️⃣ Masuk ke menu GET FILE.

2️⃣ Masukkan CODE yang diberikan.

Contoh:
ABC123XYZ

3️⃣ Sistem akan mengecek status file.

Jika GRATIS
✅ File langsung dikirim.

Jika BERBAYAR
💳 Anda harus melakukan pembayaran terlebih dahulu.

4️⃣ Setelah pembayaran berhasil,
bot akan mengirim seluruh file secara otomatis.

━━━━━━━━━━━━━━

Semua pembelian akan langsung diproses oleh sistem tanpa perlu menunggu admin.
"""
    )


# =====================================
# MONEY
# =====================================
@router.callback_query(F.data == "help_money")
async def help_money(call: CallbackQuery):

    await help_template(
        call,
        "money",
        """━━━━━━━━━━━━━━
💰 <b>CARA MENDAPATKAN CUAN</b>
━━━━━━━━━━━━━━

Bot ini memungkinkan Anda menghasilkan uang dari file yang Anda upload.

Langkah-langkah:

① Upload file.

② Tentukan harga.

Contoh:

Rp1.000
Rp2.000
Rp5.000
Rp10.000
Rp20.000
Rp50.000

③ Bot membuat CODE.

④ Sebarkan CODE tersebut ke:

• Telegram
• Facebook
• WhatsApp
• Instagram
• TikTok
• Discord
• Forum
• Website

⑤ Ketika ada orang membeli file tersebut,
saldo Anda akan otomatis masuk.

━━━━━━━━━━━━━━

Semakin banyak orang membeli file Anda,
semakin besar penghasilan yang diperoleh.

Tidak ada batas jumlah upload.

Anda dapat memiliki ratusan bahkan ribuan kode aktif sekaligus.

Semua saldo dapat dicek melalui menu ACCOUNT.
"""
    )


# =====================================
# WITHDRAW
# =====================================
@router.callback_query(F.data == "help_withdraw")
async def help_withdraw(call: CallbackQuery):

    await help_template(
        call,
        "withdraw",
        """━━━━━━━━━━━━━━
🏦 <b>CARA WITHDRAW</b>
━━━━━━━━━━━━━━

1️⃣ Pastikan saldo Anda mencukupi.

2️⃣ Masuk ke menu WITHDRAW.

3️⃣ Pilih metode pencairan.

4️⃣ Masukkan nominal withdraw.

Contoh:
10000
50000
100000

5️⃣ Masukkan nomor rekening atau e-wallet.

Contoh:

DANA
OVO
GoPay
ShopeePay
Bank BCA
Bank BRI
Bank Mandiri
Bank BNI

6️⃣ Periksa kembali data Anda.

7️⃣ Kirim permintaan Withdraw.

━━━━━━━━━━━━━━

Setelah permintaan dikirim,
admin akan memproses withdraw sesuai antrean.

Status withdraw dapat dilihat melalui menu akun.

Pastikan nama penerima dan nomor rekening sudah benar.
"""
    )


# =====================================
# VVIP
# =====================================
@router.callback_query(F.data == "help_vvip")
async def help_vvip(call: CallbackQuery):

    await help_template(
        call,
        "vvip",
        """━━━━━━━━━━━━━━
💎 <b>VVIP MEMBER</b>
━━━━━━━━━━━━━━

VVIP adalah paket premium yang memberikan berbagai keuntungan.

Keuntungan:

✅ Unlimited Buka File

✅ Prioritas Server

✅ Prioritas Support

✅ Update Fitur lebih lengkap

✅ Akses Fitur Eksklusif

✅ Sistem Lebih Stabil

✅ Performa buka file Lebih Banyak

VVIP sangat cocok bagi pengguna yang serius ingin menghasilkan uang menggunakan bot ini.

Informasi harga dapat dilihat pada menu VVIP.
"""
    )
