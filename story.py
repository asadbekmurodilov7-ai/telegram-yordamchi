"""Istorya (Telegram Stories) — Telethon userbot orqali Asadbekning SHAXSIY
profiliga story qo'yish.

Bot API shaxsiy profilga story qo'ya olmaydi, shuning uchun MTProto (Telethon)
klienti ishlatiladi. Klient Asadbekning o'z akkaunti nomidan (userbot) ishlaydi —
sessiya `story_login.py` orqali bir marta olinadi va .env dagi TG_SESSION ga yoziladi.

Muhit o'zgaruvchilari:
  TG_API_ID   - my.telegram.org -> API development tools
  TG_API_HASH - o'sha yerdan
  TG_SESSION  - story_login.py chiqargan StringSession satri (SIR SAQLANADI)
"""

import io
import logging
import os

log = logging.getLogger("story")

# Story qancha turadi (soniya): 6soat / 12soat / 24soat / 48soat dan biri bo'lishi kerak
STORY_DAVOMIYLIK = 86400

_client = None


def _env():
    """Env'ni chaqiruv paytida o'qiydi (load_dotenv dan keyin)."""
    return (
        int(os.environ.get("TG_API_ID", "0") or 0),
        os.environ.get("TG_API_HASH", ""),
        os.environ.get("TG_SESSION", ""),
    )


def sozlanganmi() -> bool:
    api_id, api_hash, session = _env()
    return bool(api_id and api_hash and session)


async def _klient():
    """Telethon klientini (bir marta) yaratadi va ulaydi."""
    global _client
    api_id, api_hash, session = _env()
    if not (api_id and api_hash and session):
        raise RuntimeError(
            "Istorya sozlanmagan: .env faylida TG_API_ID, TG_API_HASH va TG_SESSION "
            "bo'lishi kerak. Avval `python story_login.py` ni ishga tushiring."
        )
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    if _client is None:
        _client = TelegramClient(StringSession(session), api_id, api_hash)
    if not _client.is_connected():
        await _client.connect()
    if not await _client.is_user_authorized():
        raise RuntimeError(
            "Istorya sessiyasi yaroqsiz — `python story_login.py` ni qayta ishga tushirib "
            "yangi TG_SESSION oling."
        )
    return _client


def _rasmmi(nom: str, mime: str) -> bool:
    nom = (nom or "").lower()
    return mime.startswith("image/") or nom.endswith((".jpg", ".jpeg", ".png", ".webp"))


async def story_qoy(media, nom: str = "story.jpg", mime: str = "image/jpeg",
                    caption: str = "", davomiylik: int = STORY_DAVOMIYLIK) -> None:
    """Shaxsiy profilga story qo'yadi.

    media: bytes (rasm/video mazmuni) yoki fayl yo'li (str).
    nom/mime: media turini aniqlash uchun.
    caption: story ustiga yoziladigan matn (ixtiyoriy).
    """
    from telethon.tl import functions, types

    client = await _klient()

    if isinstance(media, (bytes, bytearray)):
        fayl = io.BytesIO(bytes(media))
        fayl.name = nom
        yuklangan = await client.upload_file(fayl)
    else:  # fayl yo'li
        yuklangan = await client.upload_file(media)

    if _rasmmi(nom, mime):
        media_obj = types.InputMediaUploadedPhoto(file=yuklangan)
    else:
        media_obj = types.InputMediaUploadedDocument(
            file=yuklangan,
            mime_type=mime or "video/mp4",
            attributes=[types.DocumentAttributeVideo(
                duration=0, w=0, h=0, supports_streaming=True,
            )],
        )

    await client(functions.stories.SendStoryRequest(
        peer="me",
        media=media_obj,
        privacy_rules=[types.InputPrivacyValueAllowAll()],
        caption=(caption or None),
        period=davomiylik,
    ))
    log.info("Story joylandi (nom=%s, mime=%s)", nom, mime)


def matnli_rasm(matn: str) -> bytes:
    """Matndan oddiy, chiroyli fon-rasm (1080x1920 PNG) yasaydi — matnli story uchun.

    Pillow kutubxonasi kerak. O'rnatilmagan bo'lsa RuntimeError chiqadi.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        raise RuntimeError(
            "Matnli story uchun Pillow kerak (pip install pillow), yoki /story ni "
            "rasm/videoga reply qilib ishlating."
        ) from e

    en, boy = 1080, 1920
    rasm = Image.new("RGB", (en, boy), (18, 22, 33))
    chiz = ImageDraw.Draw(rasm)

    shrift = None
    for yol in (
        "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            shrift = ImageFont.truetype(yol, 64)
            break
        except OSError:
            continue
    if shrift is None:
        shrift = ImageFont.load_default()

    # Matnni satrlarga bo'lish (taxminan 22 belgi/satr)
    sozlar, satrlar, joriy = matn.split(), [], ""
    for soz in sozlar:
        if len(joriy) + len(soz) + 1 <= 22:
            joriy = f"{joriy} {soz}".strip()
        else:
            satrlar.append(joriy)
            joriy = soz
    if joriy:
        satrlar.append(joriy)

    qator_balandligi = 90
    umumiy = len(satrlar) * qator_balandligi
    y = (boy - umumiy) // 2
    for satr in satrlar:
        quti = chiz.textbbox((0, 0), satr, font=shrift)
        w = quti[2] - quti[0]
        chiz.text(((en - w) // 2, y), satr, fill=(240, 244, 255), font=shrift)
        y += qator_balandligi

    chiqish = io.BytesIO()
    rasm.save(chiqish, format="PNG")
    return chiqish.getvalue()
