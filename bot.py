# -*- coding: utf-8 -*-
"""
Telegram yordamchi bot (Asadbek uchun)

Funksiyalar:
  - Eslatmalar        (/eslatma, /eslatmalar)
  - Ob-havo           (/obhavo Toshkent)
  - Valyuta           (/valyuta) - Markaziy bank kurslari
  - Kanal kuzatuvchi  (/kanal, /kanallar) - kanallardagi yangi qiziq postlarni egaga
                      va NEWS_KANAL'ga (rasmi bilan, bo'lsa) yuboradi
  - Qo'lda post       (/post) - o'z kanaliga matn yoki rasm joylashtirish
  - Kunlik ob-havo    - har kuni 07:00 da Farg'ona ob-havosi egaga yuboriladi
  - AI suhbat         - yozgan odamlar bilan egasining uslubida suhbatlashadi,
                      internetdan qidiruv qila oladi (web_search), yuborilgan
                      rasmni ko'ra oladi (vision)
  - AI orqali post    - ega suhbatda "kanalimga shu haqida yoz" desa, AI post
                      matnini tayyorlab tasdiq so'raydi, "ha" desa (yoki vaqt
                      aytilgan bo'lsa o'sha vaqtda) NEWS_KANAL'ga joylaydi
  - AI dayjest        - kuniga 3 mahal (09,14,20) internetdan AI yangiliklarini
                      topib kanalga dayjest joylaydi (/dayjest bilan qo'lda ham)
  - So'rovnoma        - suhbatda "kanalga so'rovnoma qo'y" desa poll joylaydi
  - Post navbati      - /navbatga bilan post qo'shiladi, har 4 soatda kanalga
  - Hujjat xulosasi   - PDF yoki matnli fayl yuborilsa Claude o'qib xulosalaydi

Muhit o'zgaruvchilari (environment variables):
  BOT_TOKEN          - BotFather bergan token (majburiy)
  ADMIN_CHAT_ID      - egasining chat raqami; /id buyrug'i bilan bilib olinadi
  ANTHROPIC_API_KEY  - Claude API kaliti (AI suhbat va qiziq postlarni saralash uchun)
"""

import os
import re
import base64
import html as html_mod
import sqlite3
import logging
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv
from telegram import BotCommand, BotCommandScopeChat, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters,
)

load_dotenv()

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("bot")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0") or 0)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DB_FILE = os.environ.get("DB_FILE", "bot.db")


def _kanal_manzili(qiymat: str):
    """'@nomi', 'nomi' yoki '-100...' ID'ni Telegram chat_id formatiga o'giradi."""
    qiymat = (qiymat or "").strip()
    if not qiymat:
        return None
    if qiymat.lstrip("-").isdigit():
        return int(qiymat)
    return qiymat if qiymat.startswith("@") else f"@{qiymat}"


NEWS_KANAL = _kanal_manzili(os.environ.get("NEWS_KANAL", ""))

VAQT_ZONASI = ZoneInfo("Asia/Tashkent")
FARGONA = {"nom": "Farg'ona", "lat": 40.3864, "lon": 71.7843}

# Egasining suhbat uslubi - bazadagi 'uslub' sozlamasi bo'lmasa shu ishlatiladi
STANDART_USLUB = (
    "Ismim Asadbek. IT va texnologiyaga qiziqaman. Erkin, oddiy so'zlashuv "
    "uslubida yozaman, lekin odamlarga hurmat bilan ('siz' deb) murojaat qilaman. "
    "Javoblarim o'rtacha uzunlikda - na juda qisqa, na juda uzun. Ko'proq jiddiy "
    "va aniq gaplashaman, hazilni kamdan-kam ishlataman."
)

# ---------------------------------------------------------------- ma'lumotlar bazasi
def db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS eslatmalar ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, matn TEXT, vaqt TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS kanallar (nom TEXT PRIMARY KEY, oxirgi_post INTEGER)"
    )
    conn.execute("CREATE TABLE IF NOT EXISTS sozlamalar (kalit TEXT PRIMARY KEY, qiymat TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS vaqtli_postlar ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, matn TEXT, vaqt TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS navbat ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, matn TEXT, qoshilgan TEXT)"
    )
    return conn


def sozlama_ol(kalit, standart=""):
    conn = db()
    qator = conn.execute("SELECT qiymat FROM sozlamalar WHERE kalit = ?", (kalit,)).fetchone()
    conn.close()
    return qator[0] if qator else standart


def sozlama_qoy(kalit, qiymat):
    conn = db()
    conn.execute(
        "INSERT INTO sozlamalar (kalit, qiymat) VALUES (?, ?) "
        "ON CONFLICT(kalit) DO UPDATE SET qiymat = ?",
        (kalit, qiymat, qiymat),
    )
    conn.commit()
    conn.close()


def egami(update: Update) -> bool:
    return ADMIN_CHAT_ID and update.effective_chat.id == ADMIN_CHAT_ID

# ---------------------------------------------------------------- /start va /yordam
YORDAM_MATNI = (
    "Salom! Men Asadbekning yordamchi botiman \U0001F916\n\n"
    "Buyruqlar:\n"
    "• /eslatma 30d Non olish - eslatma qo'shish\n"
    "• /eslatmalar - eslatmalar ro'yxati\n"
    "• /obhavo Toshkent - ob-havo\n"
    "• /valyuta - valyuta kurslari\n"
    "• /id - chat raqamingiz\n\n"
    "Shunchaki yozsangiz - suhbatlashamiz!"
)

EGA_YORDAMI = (
    "\n\nEga buyruqlari (faqat siz uchun):\n"
    "• /kanal kanal_nomi - kanalni kuzatuvga qo'shish\n"
    "• /kanal_ochir kanal_nomi - kuzatuvdan olib tashlash\n"
    "• /kanallar - kuzatilayotgan kanallar\n"
    "• /post matn - o'z kanalingizga qo'lda joylashtirish (rasmli xabarga\n"
    "  javob qilib ham ishlatsa bo'ladi)\n"
    "Har kuni 07:00 da Farg'ona ob-havosini yuboraman."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matn = YORDAM_MATNI + (EGA_YORDAMI if egami(update) else "")
    await update.message.reply_text(matn)


async def chat_id_korsat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Chat raqamingiz: {update.effective_chat.id}\n"
        "Bot egasi bo'lsangiz, buni serverda ADMIN_CHAT_ID sifatida qo'ying."
    )

# ---------------------------------------------------------------- eslatmalar
def vaqtni_ochish(soz: str):
    hozir = datetime.now(VAQT_ZONASI)
    soz = soz.strip().lower()

    m = re.fullmatch(r"(\d+)\s*(d|daqiqa|min|minut)", soz)
    if m:
        return hozir + timedelta(minutes=int(m.group(1)))

    m = re.fullmatch(r"(\d+)\s*(s|soat)", soz)
    if m:
        return hozir + timedelta(hours=int(m.group(1)))

    m = re.fullmatch(r"(\d{1,2}):(\d{2})", soz)
    if m:
        soat, daqiqa = int(m.group(1)), int(m.group(2))
        if soat < 24 and daqiqa < 60:
            vaqt = datetime.combine(hozir.date(), dtime(soat, daqiqa, tzinfo=VAQT_ZONASI))
            if vaqt <= hozir:
                vaqt += timedelta(days=1)
            return vaqt
    return None


async def eslatma_yubor(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    await context.bot.send_message(data["chat_id"], f"⏰ Eslatma: {data['matn']}")
    conn = db()
    conn.execute("DELETE FROM eslatmalar WHERE id = ?", (data["id"],))
    conn.commit()
    conn.close()


async def vaqtli_post_yubor(context: ContextTypes.DEFAULT_TYPE):
    """AI orqali taklif qilingan, vaqti belgilangan postni kanalga joylaydi."""
    data = context.job.data
    if NEWS_KANAL:
        try:
            await _postni_yubor(context.bot, NEWS_KANAL, data["matn"])
            if ADMIN_CHAT_ID:
                await context.bot.send_message(
                    ADMIN_CHAT_ID, f"✅ Vaqtli post kanalga joylandi:\n\n{data['matn']}"
                )
        except Exception as e:
            log.error("Vaqtli post yuborishda xato: %s", e)
    conn = db()
    conn.execute("DELETE FROM vaqtli_postlar WHERE id = ?", (data["id"],))
    conn.commit()
    conn.close()


async def eslatma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Yozish tartibi:\n/eslatma 30d Non olish\n/eslatma 2soat Dars\n/eslatma 18:30 Uchrashuv"
        )
        return

    vaqt = vaqtni_ochish(context.args[0])
    if not vaqt:
        await update.message.reply_text("Vaqtni tushunmadim \U0001F615 Masalan: 30d, 2soat yoki 18:30")
        return

    matn = " ".join(context.args[1:])
    chat_id = update.effective_chat.id

    conn = db()
    cur = conn.execute(
        "INSERT INTO eslatmalar (chat_id, matn, vaqt) VALUES (?, ?, ?)",
        (chat_id, matn, vaqt.isoformat()),
    )
    conn.commit()
    eslatma_id = cur.lastrowid
    conn.close()

    context.job_queue.run_once(
        eslatma_yubor, when=vaqt,
        data={"id": eslatma_id, "chat_id": chat_id, "matn": matn},
    )
    await update.message.reply_text(f"✅ {vaqt.strftime('%d.%m %H:%M')} da eslataman: {matn}")


async def eslatmalar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db()
    qatorlar = conn.execute(
        "SELECT matn, vaqt FROM eslatmalar WHERE chat_id = ? ORDER BY vaqt",
        (update.effective_chat.id,),
    ).fetchall()
    conn.close()

    if not qatorlar:
        await update.message.reply_text("Hozircha eslatmalar yo'q.")
        return
    javob = "\U0001F4CB Kutilayotgan eslatmalar:\n"
    for matn, vaqt in qatorlar:
        javob += f"• {datetime.fromisoformat(vaqt).strftime('%d.%m %H:%M')} - {matn}\n"
    await update.message.reply_text(javob)

# ---------------------------------------------------------------- ob-havo
OBHAVO_KODLARI = {
    0: "ochiq ☀️", 1: "asosan ochiq \U0001F324", 2: "qisman bulutli ⛅", 3: "bulutli ☁️",
    45: "tuman \U0001F32B", 48: "qirovli tuman \U0001F32B", 51: "mayda yomg'ir \U0001F326", 61: "yomg'ir \U0001F327",
    63: "yomg'ir \U0001F327", 65: "kuchli yomg'ir \U0001F327", 71: "qor \U0001F328", 73: "qor \U0001F328",
    75: "kuchli qor ❄️", 80: "jala \U0001F327", 95: "momaqaldiroq ⛈",
}


async def obhavo_matni(lat, lon, nom) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,weather_code",
                "timezone": "Asia/Tashkent", "forecast_days": 1,
            },
        )
    d = r.json()
    hozirgi, kunlik = d["current"], d["daily"]
    return (
        f"\U0001F30D {nom}\n"
        f"\U0001F321 Hozir: {hozirgi['temperature_2m']}°C, "
        f"{OBHAVO_KODLARI.get(hozirgi['weather_code'], '')}\n"
        f"\U0001F4C8 Bugun: {kunlik['temperature_2m_min'][0]}°C ... {kunlik['temperature_2m_max'][0]}°C\n"
        f"\U0001F4A8 Shamol: {hozirgi['wind_speed_10m']} km/soat"
    )


async def obhavo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shahar = " ".join(context.args) if context.args else "Farg'ona"
    async with httpx.AsyncClient(timeout=15) as client:
        geo = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": shahar, "count": 1, "language": "uz"},
        )
    joylar = geo.json().get("results")
    if not joylar:
        await update.message.reply_text(f"'{shahar}' topilmadi. Boshqa nom yozib ko'ring.")
        return
    joy = joylar[0]
    await update.message.reply_text(
        await obhavo_matni(joy["latitude"], joy["longitude"], joy["name"])
    )


async def kunlik_obhavo(context: ContextTypes.DEFAULT_TYPE):
    """Har kuni 07:00 da Farg'ona ob-havosini egaga yuboradi."""
    if not ADMIN_CHAT_ID:
        return
    try:
        matn = await obhavo_matni(FARGONA["lat"], FARGONA["lon"], FARGONA["nom"])
        await context.bot.send_message(ADMIN_CHAT_ID, "\U0001F305 Xayrli tong, Asadbek!\n\n" + matn)
    except Exception as e:
        log.error("Kunlik ob-havo xatosi: %s", e)

# ---------------------------------------------------------------- valyuta
async def valyuta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get("https://cbu.uz/uz/arkhiv-kursov-valyut/json/")
    kerakli = {"USD": "\U0001F1FA\U0001F1F8 Dollar", "EUR": "\U0001F1EA\U0001F1FA Yevro", "RUB": "\U0001F1F7\U0001F1FA Rubl"}
    javob = "\U0001F4B1 Markaziy bank kurslari (1 birlik = so'm):\n"
    for v in r.json():
        if v["Ccy"] in kerakli:
            javob += f"{kerakli[v['Ccy']]}: {float(v['Rate']):,.2f}\n"
    await update.message.reply_text(javob)

# ---------------------------------------------------------------- kanal kuzatuvchi
def kanal_postlarini_olish(sahifa_html: str):
    """t.me/s/ sahifasidan (post_id, matn, rasm_url) uchliklarini ajratib oladi."""
    postlar = []
    bloklar = re.split(r'class="tgme_widget_message\b', sahifa_html)[1:]
    for blok in bloklar:
        m_id = re.search(r'data-post="[^"]+/(\d+)"', blok)
        if not m_id:
            continue
        m_matn = re.search(
            r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', blok, re.S
        )
        matn = ""
        if m_matn:
            matn = re.sub(r"<br\s*/?>", "\n", m_matn.group(1))
            matn = html_mod.unescape(re.sub(r"<[^>]+>", "", matn)).strip()

        m_rasm = re.search(
            r"tgme_widget_message_photo_wrap[^>]*?style=\"[^\"]*"
            r"background-image:url\('([^']+)'\)",
            blok,
        )
        rasm = html_mod.unescape(m_rasm.group(1)) if m_rasm else None

        postlar.append((int(m_id.group(1)), matn, rasm))
    return sorted(postlar)


async def qiziqlarini_saralash(kanal: str, postlar: list) -> str:
    """AI orqali yangi postlardan qiziqlarini tanlab, qisqa xulosa qiladi."""
    royxat = "\n\n".join(f"[Post {pid}]\n{matn[:800]}" for pid, matn, _ in postlar if matn)
    if not royxat:
        return ""
    if not ANTHROPIC_API_KEY:
        # AI bo'lmasa - hammasini qisqartirib yuboramiz
        return "\n\n".join(f"• {matn[:300]}" for _, matn, _ in postlar if matn)

    uslub_matni = sozlama_ol("uslub", STANDART_USLUB)

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    javob = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=800,
        system=(
            "Sen Telegram kanallarini kuzatuvchi yordamchisan. Quyida kanaldagi yangi "
            "postlar berilgan. Faqat chindan qiziqarli va foydali postlarni tanla va har "
            "birini 1-2 jumlada o'zbek tilida xulosala. Reklama va ahamiyatsiz postlarni "
            "tashlab yubor. Agar hech biri qiziq bo'lmasa, faqat 'YOQ' deb yoz.\n\n"
            "Xulosalarni quruq/rasmiy botdek emas, balki quyidagi uslubdagi odam "
            "o'zi yozgandek, uning ovozida yoz:\n"
            f"{uslub_matni}"
        ),
        messages=[{"role": "user", "content": f"Kanal: @{kanal}\n\n{royxat}"}],
    )
    natija = javob.content[0].text.strip()
    return "" if natija.upper().startswith("YOQ") else natija


async def _postni_yubor(bot, chat_id, matn: str, rasm_url: str | None = None):
    """Matnni (imkon bo'lsa rasm bilan birga) chatga/kanalga yuboradi."""
    if rasm_url:
        try:
            if len(matn) <= 1024:
                await bot.send_photo(chat_id, photo=rasm_url, caption=matn)
                return
            await bot.send_photo(chat_id, photo=rasm_url)
        except Exception as e:
            log.error("Rasm yuborishda xato, faqat matn yuboriladi: %s", e)
    await bot.send_message(chat_id, matn)


async def kanallarni_tekshir(context: ContextTypes.DEFAULT_TYPE):
    """Soatiga bir marta kanallarni tekshirib, yangi qiziq postlarni egaga yuboradi."""
    if not ADMIN_CHAT_ID:
        return
    conn = db()
    kanallar = conn.execute("SELECT nom, oxirgi_post FROM kanallar").fetchall()
    conn.close()

    for nom, oxirgi in kanallar:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                r = await client.get(
                    f"https://t.me/s/{nom}",
                    headers={"User-Agent": "Mozilla/5.0"},
                )
            postlar = kanal_postlarini_olish(r.text)
            if not postlar:
                continue

            eng_yangi = postlar[-1][0]
            yangilar = [(pid, m, img) for pid, m, img in postlar if pid > oxirgi]

            conn = db()
            conn.execute("UPDATE kanallar SET oxirgi_post = ? WHERE nom = ?", (eng_yangi, nom))
            conn.commit()
            conn.close()

            if oxirgi == 0 or not yangilar:   # birinchi tekshiruvda eski postlarni yubormaymiz
                continue

            soxrolar = yangilar[-5:]
            xulosa = await qiziqlarini_saralash(nom, soxrolar)
            if xulosa:
                matn = (
                    f"\U0001F4E2 @{nom} kanalida yangi qiziq postlar:\n\n{xulosa}\n\n"
                    f"\U0001F517 https://t.me/{nom}"
                )
                rasm = next((img for _, _, img in reversed(soxrolar) if img), None)
                await _postni_yubor(context.bot, ADMIN_CHAT_ID, matn, rasm)
                if NEWS_KANAL:
                    try:
                        await _postni_yubor(context.bot, NEWS_KANAL, matn, rasm)
                    except Exception as e:
                        log.error("Yangiliklar kanaliga yuborishda xato: %s", e)
        except Exception as e:
            log.error("Kanal tekshirish xatosi (%s): %s", nom, e)


async def ai_dayjest(context: ContextTypes.DEFAULT_TYPE):
    """Kuniga bir necha marta internetdan AI yangiliklarini topib kanalga dayjest joylaydi."""
    if not NEWS_KANAL or not ANTHROPIC_API_KEY:
        return
    uslub_matni = sozlama_ol("uslub", STANDART_USLUB)
    oldingi = sozlama_ol("dayjest_xotira", "")
    oldingi_matn = oldingi if oldingi else "(hali dayjest yo'q)"

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    try:
        javob = await client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1500,
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 4}],
            system=(
                "Sen AI (sun'iy intellekt) mavzusidagi Telegram kanali uchun kontent "
                "tayyorlaysan. Vazifang: internetdan bugungi eng muhim va so'nggi AI "
                "yangiliklarini qidirib top (web_search ishlatib), ulardan 3-5 tasini "
                "tanla va o'zbek tilida qisqa, qiziqarli dayjest post yoz. Har yangilikni "
                "1-2 jumlada ber, mos emoji bilan chiroyli formatla. Post boshida qisqa "
                "sarlavha bo'lsin (masalan '\U0001F916 Bugungi AI yangiliklari').\n\n"
                "Postni quyidagi uslubdagi odam o'zi yozgandek, uning ovozida yoz:\n"
                f"{uslub_matni}\n\n"
                "MUHIM: quyidagi mavzular oldingi dayjestlarda berilgan - ularni "
                f"TAKRORLAMA, faqat yangi yangiliklarni ber:\n{oldingi_matn}\n\n"
                "Agar hech qanday yangi muhim AI yangiligi topilmasa, faqat 'YOQ' deb yoz. "
                "Aks holda faqat postning o'zini yoz, boshqa hech qanday izoh qo'shma."
            ),
            messages=[{
                "role": "user",
                "content": "Bugungi eng so'nggi AI yangiliklari dayjestini tayyorla.",
            }],
        )
        post = "\n".join(
            b.text for b in javob.content if getattr(b, "type", None) == "text"
        ).strip()
        if not post or post.upper().startswith("YOQ"):
            log.info("AI dayjest: yangi yangilik topilmadi")
            return

        await _postni_yubor(context.bot, NEWS_KANAL, post)
        # Takrorlashning oldini olish uchun oxirgi dayjestlarni eslab qolamiz
        yangi_xotira = (post[:700] + "\n---\n" + oldingi)[:2500]
        sozlama_qoy("dayjest_xotira", yangi_xotira)
        if ADMIN_CHAT_ID:
            await context.bot.send_message(
                ADMIN_CHAT_ID, f"\U0001F4F0 AI dayjest kanalingizga joylandi:\n\n{post}"
            )
    except Exception as e:
        log.error("AI dayjest xatosi: %s", e)


async def dayjest_buyrug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Qo'lda AI dayjestni hozir tayyorlab kanalga joylaydi (sinov uchun)."""
    if not egami(update):
        await update.message.reply_text("Bu buyruq faqat bot egasi uchun.")
        return
    await update.message.reply_text("\U0001F50D AI yangiliklarini qidiryapman, biroz kuting...")
    await ai_dayjest(context)


async def kanal_qosh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not egami(update):
        await update.message.reply_text("Bu buyruq faqat bot egasi uchun.")
        return
    if not context.args:
        await update.message.reply_text(
            "Kanal nomini yozing, masalan:\n/kanal kunuz\n(faqat ochiq kanallar ishlaydi)"
        )
        return
    nom = context.args[0].lstrip("@").replace("https://t.me/", "").strip("/")
    conn = db()
    conn.execute(
        "INSERT INTO kanallar (nom, oxirgi_post) VALUES (?, 0) "
        "ON CONFLICT(nom) DO NOTHING", (nom,)
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ @{nom} kuzatuvga qo'shildi! Yangi qiziq postlarni sizga yuborib turaman."
    )


async def kanal_ochir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not egami(update):
        await update.message.reply_text("Bu buyruq faqat bot egasi uchun.")
        return
    if not context.args:
        await update.message.reply_text("Kanal nomini yozing: /kanal_ochir kunuz")
        return
    nom = context.args[0].lstrip("@")
    conn = db()
    conn.execute("DELETE FROM kanallar WHERE nom = ?", (nom,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"\U0001F5D1 @{nom} kuzatuvdan olib tashlandi.")


async def kanallar_royxati(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not egami(update):
        await update.message.reply_text("Bu buyruq faqat bot egasi uchun.")
        return
    conn = db()
    qatorlar = conn.execute("SELECT nom FROM kanallar").fetchall()
    conn.close()
    if not qatorlar:
        await update.message.reply_text("Kuzatilayotgan kanal yo'q. /kanal nomi bilan qo'shing.")
        return
    await update.message.reply_text(
        "\U0001F4E1 Kuzatilayotgan kanallar:\n" + "\n".join(f"• @{q[0]}" for q in qatorlar)
    )


async def post_qil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Egaga tegishli NEWS_KANAL'ga qo'lda matn/rasm joylashtiradi."""
    if not egami(update):
        await update.message.reply_text("Bu buyruq faqat bot egasi uchun.")
        return
    if not NEWS_KANAL:
        await update.message.reply_text(
            "Avval .env faylida NEWS_KANAL sozlamasini to'ldiring (kanal @username'i)."
        )
        return

    qoshimcha = " ".join(context.args) if context.args else ""
    javob_uchun = update.message.reply_to_message

    try:
        if javob_uchun and javob_uchun.photo:
            caption = qoshimcha or javob_uchun.caption or ""
            await context.bot.send_photo(
                NEWS_KANAL, photo=javob_uchun.photo[-1].file_id, caption=caption[:1024] or None
            )
        elif javob_uchun and (javob_uchun.text or javob_uchun.caption):
            matn = qoshimcha or javob_uchun.text or javob_uchun.caption
            await context.bot.send_message(NEWS_KANAL, matn)
        elif qoshimcha:
            await context.bot.send_message(NEWS_KANAL, qoshimcha)
        else:
            await update.message.reply_text(
                "Nima joylashni ayting:\n"
                "• /post Matningiz\n"
                "• Rasmli yoki matnli xabarga javob (reply) qilib /post deb yozing\n"
                "  (reply + /post izoh - izoh caption o'rnini bosadi)"
            )
            return
    except Exception as e:
        log.error("Kanalga post xatosi: %s", e)
        await update.message.reply_text(
            "Kanalga joylab bo'lmadi. Bot kanalda admin ekanini va \"Post Messages\" "
            "huquqi borligini tekshiring."
        )
        return

    await update.message.reply_text(f"✅ {NEWS_KANAL} ga joylandi!")


# ---------------------------------------------------------------- post navbati
async def navbatga_qosh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Postni navbatga qo'shadi - bot uni kun davomida avtomatik joylaydi."""
    if not egami(update):
        await update.message.reply_text("Bu buyruq faqat bot egasi uchun.")
        return
    matn = " ".join(context.args) if context.args else ""
    javob_uchun = update.message.reply_to_message
    if not matn and javob_uchun:
        matn = javob_uchun.text or javob_uchun.caption or ""
    if not matn.strip():
        await update.message.reply_text(
            "Navbatga qo'shish uchun:\n/navbatga Post matni\n"
            "yoki matnli xabarga javob qilib /navbatga deb yozing."
        )
        return
    conn = db()
    conn.execute(
        "INSERT INTO navbat (matn, qoshilgan) VALUES (?, ?)",
        (matn.strip(), datetime.now(VAQT_ZONASI).isoformat()),
    )
    soni = conn.execute("SELECT COUNT(*) FROM navbat").fetchone()[0]
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ Navbatga qo'shildi (navbatda {soni} ta post). "
        "Kunduzi har 4 soatda bittadan avtomatik joylayman."
    )


async def navbat_korsat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navbatdagi postlar ro'yxatini ko'rsatadi."""
    if not egami(update):
        await update.message.reply_text("Bu buyruq faqat bot egasi uchun.")
        return
    conn = db()
    qatorlar = conn.execute("SELECT id, matn FROM navbat ORDER BY id").fetchall()
    conn.close()
    if not qatorlar:
        await update.message.reply_text(
            "Navbat bo'sh. /navbatga bilan post qo'shing.\n"
            "Tozalash uchun: /navbat_tozala"
        )
        return
    javob = f"\U0001F4CB Navbatda {len(qatorlar)} ta post:\n\n"
    for i, (pid, matn) in enumerate(qatorlar, 1):
        javob += f"{i}. {matn[:80]}{'...' if len(matn) > 80 else ''}\n"
    javob += "\nTozalash uchun: /navbat_tozala"
    await update.message.reply_text(javob)


async def navbat_tozala(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navbatni to'liq tozalaydi."""
    if not egami(update):
        await update.message.reply_text("Bu buyruq faqat bot egasi uchun.")
        return
    conn = db()
    conn.execute("DELETE FROM navbat")
    conn.commit()
    conn.close()
    await update.message.reply_text("\U0001F5D1 Navbat tozalandi.")


async def navbatni_joyla(context: ContextTypes.DEFAULT_TYPE):
    """Kunduzi har 4 soatda navbatdan bitta postni kanalga joylaydi."""
    if not NEWS_KANAL:
        return
    soat = datetime.now(VAQT_ZONASI).hour
    if soat < 8 or soat >= 23:   # kechasi joylamaymiz
        return
    conn = db()
    qator = conn.execute("SELECT id, matn FROM navbat ORDER BY id LIMIT 1").fetchone()
    conn.close()
    if not qator:
        return
    pid, matn = qator
    try:
        await _postni_yubor(context.bot, NEWS_KANAL, matn)
        conn = db()
        conn.execute("DELETE FROM navbat WHERE id = ?", (pid,))
        qoldi = conn.execute("SELECT COUNT(*) FROM navbat").fetchone()[0]
        conn.commit()
        conn.close()
        if ADMIN_CHAT_ID:
            await context.bot.send_message(
                ADMIN_CHAT_ID,
                f"\U0001F4E4 Navbatdagi post kanalga joylandi (navbatda yana {qoldi} ta):\n\n{matn[:300]}",
            )
    except Exception as e:
        log.error("Navbatdagi postni joylashda xato: %s", e)


def xabar_matni(msg) -> str:
    """Xabardan matnni oladi - forward, caption va reply kontekstini ham qo'shadi."""
    matn = msg.text or msg.caption or ""

    # Forward qilingan post bo'lsa - manbasini ko'rsatamiz
    if msg.forward_origin is not None:
        manba = "noma'lum manba"
        chat = getattr(msg.forward_origin, "chat", None)
        odam = getattr(msg.forward_origin, "sender_user", None)
        yashirin = getattr(msg.forward_origin, "sender_user_name", None)
        if chat is not None:
            manba = f"@{chat.username}" if chat.username else (chat.title or manba)
        elif odam is not None:
            manba = odam.first_name or manba
        elif yashirin:
            manba = yashirin
        matn = f"[{manba} dan forward qilingan post]:\n{matn}" if matn else (
            f"[{manba} dan forward qilingan post - matni yo'q, faqat media]"
        )

    # Boshqa xabarga javoban yozilgan bo'lsa - o'sha xabarni kontekst qilamiz
    if msg.reply_to_message is not None:
        r = msg.reply_to_message
        r_matn = r.text or r.caption or ""
        if r_matn:
            matn = (
                f"[Quyidagi xabarga javoban yozilmoqda]:\n{r_matn[:1500]}\n\n"
                f"[Xabar]:\n{matn}"
            )

    return matn.strip()


POST_TAKLIF_TOOL = {
    "name": "post_taklif",
    "description": (
        "Foydalanuvchi o'z Telegram kanaliga post joylashni so'raganda chaqir - "
        "masalan 'kanalimga shu haqida yoz', 'buni postla', 'ertaga soat 9da post "
        "qil' kabi so'rovlarda. Postning tayyor matnini o'zing yoz (foydalanuvchining "
        "uslubida), keyin shu tool orqali taklif qil - postni to'g'ridan-to'g'ri sen "
        "joylamaysan, bot foydalanuvchidan tasdiq so'raydi."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "matn": {
                "type": "string",
                "description": "Kanalga joylanadigan tayyor post matni.",
            },
            "vaqt": {
                "type": "string",
                "description": (
                    "Post qachon joylansin - foydalanuvchi vaqt aytmagan bo'lsa "
                    "bo'sh qoldir (hozir joylanadi). Masalan '30d' (daqiqa), "
                    "'2soat', '18:30'."
                ),
            },
        },
        "required": ["matn"],
    },
}

SOROVNOMA_TAKLIF_TOOL = {
    "name": "sorovnoma_taklif",
    "description": (
        "Foydalanuvchi kanaliga so'rovnoma (poll) joylashni so'raganda chaqir - "
        "masalan 'kanalga so'rovnoma qo'y', 'ovoz berish qo'shamiz' kabi so'rovlarda. "
        "Savol va 2-10 ta javob variantini o'zing tayyorlab shu tool orqali taklif "
        "qil - poll'ni to'g'ridan-to'g'ri sen joylamaysan, bot tasdiq so'raydi."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "savol": {"type": "string", "description": "So'rovnoma savoli (300 belgigacha)."},
            "variantlar": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2 tadan 10 tagacha javob varianti (har biri 100 belgigacha).",
            },
        },
        "required": ["savol", "variantlar"],
    },
}

TASDIQ_SOZLARI = {"ha", "xa", "ha.", "mayli", "ok", "ok.", "tasdiqlayman", "joyla", "joylayver", "ha joyla"}
BEKOR_SOZLARI = {"yo'q", "yoq", "yo'q.", "yoq.", "bekor", "bekor qil", "kerak emas", "yo'q kerak emas"}


async def _rasm_kontenti(msg) -> list:
    """Xabardagi rasmni Claude vision uchun base64 blokka aylantiradi."""
    if not msg.photo:
        return []
    try:
        fayl = await msg.photo[-1].get_file()
        baytlar = await fayl.download_as_bytearray()
        return [{
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.b64encode(bytes(baytlar)).decode(),
            },
        }]
    except Exception as e:
        log.error("Rasmni yuklashda xato: %s", e)
        return []


async def _hujjat_kontenti(msg):
    """PDF/matnli hujjatni Claude uchun tayyorlaydi. (bloklar, qoshimcha_matn) qaytaradi."""
    hujjat = msg.document
    if not hujjat:
        return [], ""
    nom = (hujjat.file_name or "").lower()
    turi = hujjat.mime_type or ""
    if hujjat.file_size and hujjat.file_size > 20 * 1024 * 1024:
        return [], "[Hujjat juda katta - 20MB dan oshmasligi kerak]"
    try:
        fayl = await hujjat.get_file()
        baytlar = bytes(await fayl.download_as_bytearray())
    except Exception as e:
        log.error("Hujjatni yuklashda xato: %s", e)
        return [], ""

    if turi == "application/pdf" or nom.endswith(".pdf"):
        return [{
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.b64encode(baytlar).decode(),
            },
        }], ""

    if turi.startswith("text/") or nom.endswith((".txt", ".md", ".csv", ".json")):
        matn = baytlar.decode("utf-8", errors="ignore")[:20000]
        return [], f"[Yuborilgan hujjat matni]:\n{matn}"

    return [], "[Bu hujjat turini o'qiy olmayman - PDF yoki matnli fayl yuboring]"


async def ovoz_javob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ovozli xabar kelganda - hozircha matnga o'gira olmasligimizni bildiradi."""
    msg = update.effective_message
    if msg is None:
        return
    biznesmi = update.business_message is not None
    if biznesmi and msg.from_user and msg.from_user.id == ADMIN_CHAT_ID:
        return
    try:
        await msg.reply_text(
            "Ovozli xabarni hozircha matnga o'girolmayman \U0001F615 "
            "Iltimos, yozib yuboring - darrov javob beraman."
        )
    except Exception:
        pass


# ---------------------------------------------------------------- AI suhbat
async def ai_javob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg is None:
        return

    kirish = xabar_matni(msg)
    if not kirish and not msg.photo and not msg.document:
        return

    biznesmi = update.business_message is not None
    # Biznes chatda egasining o'zi yozgan xabarlarga javob bermaymiz
    if biznesmi and msg.from_user and msg.from_user.id == ADMIN_CHAT_ID:
        return

    # Kanalga post joylash/rejalashtirish faqat egasining o'z shaxsiy chatida
    amal_ruxsat = egami(update) and not biznesmi

    if not ANTHROPIC_API_KEY:
        if not biznesmi:
            await msg.reply_text(
                "Hozir suhbatlasha olmayman (AI o'chiq). Buyruqlar uchun /yordam yozing."
            )
        return

    # Kutilayotgan post tasdig'iga javob bo'lsa
    kutilayotgan = context.chat_data.get("kutilayotgan_post")
    if kutilayotgan and amal_ruxsat:
        soz = kirish.strip().lower()
        if soz in TASDIQ_SOZLARI:
            del context.chat_data["kutilayotgan_post"]
            if not NEWS_KANAL:
                await msg.reply_text("NEWS_KANAL sozlanmagan, joylay olmayman.")
                return
            vaqt_iso = kutilayotgan.get("vaqt")
            if vaqt_iso:
                vaqt = datetime.fromisoformat(vaqt_iso)
                conn = db()
                cur = conn.execute(
                    "INSERT INTO vaqtli_postlar (matn, vaqt) VALUES (?, ?)",
                    (kutilayotgan["matn"], vaqt.isoformat()),
                )
                conn.commit()
                pid = cur.lastrowid
                conn.close()
                context.job_queue.run_once(
                    vaqtli_post_yubor, when=vaqt, data={"id": pid, "matn": kutilayotgan["matn"]}
                )
                await msg.reply_text(f"✅ {vaqt.strftime('%d.%m %H:%M')} da kanalga joylayman.")
            else:
                try:
                    await _postni_yubor(context.bot, NEWS_KANAL, kutilayotgan["matn"])
                    await msg.reply_text("✅ Kanalga joylandi!")
                except Exception as e:
                    log.error("Post joylashda xato: %s", e)
                    await msg.reply_text("Kanalga joylashda xatolik yuz berdi.")
            return
        if soz in BEKOR_SOZLARI:
            del context.chat_data["kutilayotgan_post"]
            await msg.reply_text("Bekor qildim.")
            return
        # boshqa narsa yozsa - taklifni saqlab qolamiz, suhbat davom etadi

    # Kutilayotgan so'rovnoma tasdig'iga javob bo'lsa
    kutilayotgan_soz = context.chat_data.get("kutilayotgan_sorovnoma")
    if kutilayotgan_soz and amal_ruxsat:
        soz = kirish.strip().lower()
        if soz in TASDIQ_SOZLARI:
            del context.chat_data["kutilayotgan_sorovnoma"]
            if not NEWS_KANAL:
                await msg.reply_text("NEWS_KANAL sozlanmagan, joylay olmayman.")
                return
            try:
                await context.bot.send_poll(
                    NEWS_KANAL,
                    question=kutilayotgan_soz["savol"][:300],
                    options=[v[:100] for v in kutilayotgan_soz["variantlar"][:10]],
                    is_anonymous=True,
                )
                await msg.reply_text("✅ So'rovnoma kanalga joylandi!")
            except Exception as e:
                log.error("So'rovnoma joylashda xato: %s", e)
                await msg.reply_text("So'rovnoma joylashda xatolik yuz berdi.")
            return
        if soz in BEKOR_SOZLARI:
            del context.chat_data["kutilayotgan_sorovnoma"]
            await msg.reply_text("Bekor qildim.")
            return

    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING,
            business_connection_id=msg.business_connection_id,
        )
    except Exception:
        pass

    rasm_bloklari = await _rasm_kontenti(msg)
    hujjat_bloklari, hujjat_matn = await _hujjat_kontenti(msg)

    joriy_matn = kirish or ""
    if hujjat_matn:
        joriy_matn = (joriy_matn + "\n\n" + hujjat_matn).strip()
    if not joriy_matn:
        if rasm_bloklari:
            joriy_matn = "Bu rasmga izoh bering yoki nima ekanini ayting."
        elif hujjat_bloklari:
            joriy_matn = "Bu hujjatni o'zbekchada qisqacha xulosalab bering."
        else:
            joriy_matn = "..."

    media_bloklari = hujjat_bloklari + rasm_bloklari
    joriy_kontent = (
        media_bloklari + [{"type": "text", "text": joriy_matn}] if media_bloklari else joriy_matn
    )

    tarix = context.chat_data.setdefault("tarix", [])
    sorov = tarix + [{"role": "user", "content": joriy_kontent}]

    uslub_matni = sozlama_ol("uslub", STANDART_USLUB)
    kim = update.effective_user.first_name or "foydalanuvchi"

    if biznesmi:
        qoshimcha = (
            "Bu Asadbekning SHAXSIY chati - sening javoblaring uning o'z akkauntidan "
            "yuboriladi, shuning uchun to'liq uning nomidan, birinchi shaxsda gaplash. "
            "Asadbek hozir band, o'zi bo'shagach javob berishi mumkinligini kerak "
            "bo'lganda ayt."
        )
    else:
        qoshimcha = (
            "O'zingni AI ekaningni aytishing shart emas, lekin to'g'ridan-"
            "to'g'ri so'rashsa, Asadbekning yordamchi boti ekaningni halol ayt."
        )

    toollar = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}]
    post_yordam = ""
    if amal_ruxsat and NEWS_KANAL:
        toollar.append(POST_TAKLIF_TOOL)
        toollar.append(SOROVNOMA_TAKLIF_TOOL)
        post_yordam = (
            "\n\nMUHIM: Agar Asadbek 'kanalimga yoz', 'buni postla', 'post qil', "
            "'kanalga joyla' kabi so'rov bersa - hech qachon post matnini oddiy "
            "javob sifatida yozib qo'ya qolma. Har doim post_taklif toolini "
            "chaqir, hatto post yozish uchun avval web_search ishlatgan bo'lsang ham. "
            "Agar 'kanalga so'rovnoma qo'y', 'ovoz berish qo'shamiz' kabi so'rov "
            "bersa - sorovnoma_taklif toolini chaqir."
        )

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    try:
        javob = await client.messages.create(
            model="claude-sonnet-5",
            max_tokens=2048,
            tools=toollar,
            system=(
                "Sen Asadbekning Telegram yordamchi botisan va odamlar bilan xuddi "
                "Asadbekning o'zidek suhbatlashasan. Uning uslubi haqida:\n"
                f"{uslub_matni}\n\n"
                f"Hozir sen bilan '{kim}' ismli odam yozishmoqda. Foydalanuvchi qaysi "
                "tilda yozsa, o'sha tilda javob ber (asosan o'zbekcha). Javoblaring "
                "qisqa, tabiiy va samimiy bo'lsin - xuddi oddiy odam Telegramda "
                "yozgandek.\n\n"
                "Senda internetdan qidiruv qilish imkoniyati (web_search) bor - "
                "joriy voqealar, narxlar, yangiliklar yoki aniq faktlar so'ralsa, "
                "taxmin qilmasdan avval qidir, keyin javob ber. Oddiy suhbat "
                "savollarida qidiruv shart emas.\n\n"
                "Senga rasm yuborilishi mumkin - uni ko'rasan, tahlil qil va "
                "so'ralganini bajar (tasvirlash, matnini o'qish, izoh berish va h.k.).\n\n"
                "Senga PDF yoki matnli hujjat ham yuborilishi mumkin - uni to'liq "
                "o'qiysan. So'ralsa xulosala, savollarga javob ber yoki tahlil qil.\n\n"
                "Agar xabar '[... dan forward qilingan post]' bilan boshlansa, bu "
                "foydalanuvchi senga yuborgan post matni - sen uni to'liq ko'rayapsan. "
                "'Ko'ra olmayman' dema! U bilan bemalol ishla: tahlil qil, qayta yoz, "
                "moslashtir - nima so'ralsa shuni qil. Agar forward'da '[matni yo'q, "
                "faqat media]' deyilsa, postda faqat rasm/video borligini aytib, matnini "
                f"yuborishni so'ra.\n\n{qoshimcha}{post_yordam}"
            ),
            messages=sorov,
        )
        matnlar = [b.text for b in javob.content if getattr(b, "type", None) == "text"]
        asosiy_matn = "\n".join(matnlar).strip()

        def tool_bloki(nom):
            return next(
                (b for b in javob.content
                 if getattr(b, "type", None) == "tool_use" and b.name == nom),
                None,
            )

        post_bloki = tool_bloki("post_taklif")
        sorovnoma_bloki = tool_bloki("sorovnoma_taklif")

        if post_bloki is not None:
            taklif_matn = (post_bloki.input.get("matn") or "").strip()
            vaqt_soz = (post_bloki.input.get("vaqt") or "").strip()
            vaqt_obj = vaqtni_ochish(vaqt_soz) if vaqt_soz else None
            context.chat_data["kutilayotgan_post"] = {
                "matn": taklif_matn,
                "vaqt": vaqt_obj.isoformat() if vaqt_obj else None,
            }
            vaqt_izoh = (
                f"\U0001F552 Vaqti: {vaqt_obj.strftime('%d.%m %H:%M')}"
                if vaqt_obj else "\U0001F552 Hozir joylanadi"
            )
            matn = (
                (asosiy_matn + "\n\n" if asosiy_matn else "") +
                f"\U0001F4CB Taklif etilayotgan post:\n\n{taklif_matn}\n\n{vaqt_izoh}\n\n"
                "Joylashni istasangiz \"ha\", bekor qilish uchun \"yo'q\" deb yozing."
            )
        elif sorovnoma_bloki is not None:
            savol = (sorovnoma_bloki.input.get("savol") or "").strip()
            variantlar = [
                str(v).strip() for v in (sorovnoma_bloki.input.get("variantlar") or [])
                if str(v).strip()
            ]
            if savol and len(variantlar) >= 2:
                context.chat_data["kutilayotgan_sorovnoma"] = {
                    "savol": savol, "variantlar": variantlar,
                }
                variant_matn = "\n".join(f"  • {v}" for v in variantlar)
                matn = (
                    (asosiy_matn + "\n\n" if asosiy_matn else "") +
                    f"\U0001F4CA Taklif etilayotgan so'rovnoma:\n\n"
                    f"❓ {savol}\n{variant_matn}\n\n"
                    "Joylashni istasangiz \"ha\", bekor qilish uchun \"yo'q\" deb yozing."
                )
            else:
                matn = asosiy_matn or "So'rovnoma uchun savol va kamida 2 ta variant kerak."
        else:
            matn = asosiy_matn or "Hozir javob shakllantirolmadim, boshqacharoq so'rab ko'ring \U0001F615"
    except Exception as e:
        log.error("AI xatosi: %s", e)
        if not biznesmi:
            await msg.reply_text("Hozir javob berolmayman, keyinroq yozing \U0001F615")
        return

    if kirish:
        tarix_belgi = kirish
    elif msg.document:
        tarix_belgi = "[hujjat yubordi]"
    else:
        tarix_belgi = "[rasm yubordi]"
    tarix.append({"role": "user", "content": tarix_belgi})
    tarix.append({"role": "assistant", "content": matn})
    del tarix[:-10]
    await msg.reply_text(matn)

UMUMIY_BUYRUQLAR = [
    BotCommand("start", "Botni ishga tushirish"),
    BotCommand("yordam", "Buyruqlar ro'yxati"),
    BotCommand("eslatma", "Eslatma qo'shish"),
    BotCommand("eslatmalar", "Eslatmalar ro'yxati"),
    BotCommand("obhavo", "Ob-havo ma'lumoti"),
    BotCommand("valyuta", "Valyuta kurslari"),
    BotCommand("id", "Chat raqamini ko'rish"),
]

EGA_BUYRUQLARI = UMUMIY_BUYRUQLAR + [
    BotCommand("kanal", "Kanalni kuzatuvga qo'shish"),
    BotCommand("kanal_ochir", "Kanalni kuzatuvdan olib tashlash"),
    BotCommand("kanallar", "Kuzatilayotgan kanallar"),
    BotCommand("post", "Kanalga qo'lda matn/rasm joylash"),
    BotCommand("dayjest", "AI yangiliklar dayjestini hozir joylash"),
    BotCommand("navbatga", "Postni navbatga qo'shish"),
    BotCommand("navbat", "Post navbatini ko'rish"),
    BotCommand("navbat_tozala", "Navbatni tozalash"),
]

# ---------------------------------------------------------------- ishga tushirish
async def ishga_tushganda(app: Application):
    """Bot qayta yoqilganda eslatmalarni tiklaydi."""
    await app.bot.set_my_commands(UMUMIY_BUYRUQLAR)
    if ADMIN_CHAT_ID:
        await app.bot.set_my_commands(
            EGA_BUYRUQLARI, scope=BotCommandScopeChat(ADMIN_CHAT_ID)
        )

    conn = db()
    qatorlar = conn.execute("SELECT id, chat_id, matn, vaqt FROM eslatmalar").fetchall()
    conn.close()
    hozir = datetime.now(VAQT_ZONASI)
    for eid, chat_id, matn, vaqt in qatorlar:
        v = datetime.fromisoformat(vaqt)
        if v.tzinfo is None:
            v = v.replace(tzinfo=VAQT_ZONASI)
        if v <= hozir:
            v = hozir + timedelta(seconds=10)
        app.job_queue.run_once(
            eslatma_yubor, when=v, data={"id": eid, "chat_id": chat_id, "matn": matn}
        )
    log.info("%d ta eslatma tiklandi", len(qatorlar))

    conn = db()
    postlar = conn.execute("SELECT id, matn, vaqt FROM vaqtli_postlar").fetchall()
    conn.close()
    for pid, matn, vaqt in postlar:
        v = datetime.fromisoformat(vaqt)
        if v.tzinfo is None:
            v = v.replace(tzinfo=VAQT_ZONASI)
        if v <= hozir:
            v = hozir + timedelta(seconds=10)
        app.job_queue.run_once(vaqtli_post_yubor, when=v, data={"id": pid, "matn": matn})
    log.info("%d ta vaqtli post tiklandi", len(postlar))

    if not ADMIN_CHAT_ID:
        log.warning(
            "ADMIN_CHAT_ID qo'yilmagan! Kunlik ob-havo va kanal xabarlari ishlamaydi. "
            "Botga /id yozib raqamingizni bilib oling."
        )


def main():
    if not BOT_TOKEN:
        raise SystemExit("Xato: BOT_TOKEN muhit o'zgaruvchisi qo'yilmagan!")

    app = Application.builder().token(BOT_TOKEN).post_init(ishga_tushganda).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yordam", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("id", chat_id_korsat))
    app.add_handler(CommandHandler("eslatma", eslatma))
    app.add_handler(CommandHandler("eslatmalar", eslatmalar))
    app.add_handler(CommandHandler("obhavo", obhavo))
    app.add_handler(CommandHandler("valyuta", valyuta))
    app.add_handler(CommandHandler("kanal", kanal_qosh))
    app.add_handler(CommandHandler("kanal_ochir", kanal_ochir))
    app.add_handler(CommandHandler("kanallar", kanallar_royxati))
    app.add_handler(CommandHandler("post", post_qil))
    app.add_handler(CommandHandler("dayjest", dayjest_buyrug))
    app.add_handler(CommandHandler("navbatga", navbatga_qosh))
    app.add_handler(CommandHandler("navbat", navbat_korsat))
    app.add_handler(CommandHandler("navbat_tozala", navbat_tozala))
    app.add_handler(MessageHandler(
        ((filters.TEXT | filters.CAPTION | filters.FORWARDED | filters.PHOTO
          | filters.Document.ALL) & ~filters.COMMAND)
        & (filters.UpdateType.MESSAGE | filters.UpdateType.BUSINESS_MESSAGE),
        ai_javob,
    ))
    app.add_handler(MessageHandler(
        (filters.VOICE | filters.AUDIO)
        & (filters.UpdateType.MESSAGE | filters.UpdateType.BUSINESS_MESSAGE),
        ovoz_javob,
    ))

    # Har kuni 07:00 (Toshkent vaqti) - Farg'ona ob-havosi
    app.job_queue.run_daily(kunlik_obhavo, time=dtime(7, 0, tzinfo=VAQT_ZONASI))
    # Har soatda - kanallarni tekshirish (birinchisi 1 daqiqadan keyin)
    app.job_queue.run_repeating(kanallarni_tekshir, interval=3600, first=60)
    # Kuniga 3 mahal - AI yangiliklar dayjesti kanalga
    for soat in (9, 14, 20):
        app.job_queue.run_daily(ai_dayjest, time=dtime(soat, 0, tzinfo=VAQT_ZONASI))
    # Har 4 soatda - navbatdan bitta post (kunduzi)
    app.job_queue.run_repeating(navbatni_joyla, interval=4 * 3600, first=120)

    log.info("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
