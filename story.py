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
                    caption: str = "", davomiylik: int = STORY_DAVOMIYLIK,
                    video_uzunlik: int = 0, en: int = 1080, boy: int = 1920) -> None:
    """Shaxsiy profilga story qo'yadi.

    media: bytes (rasm/video mazmuni) yoki fayl yo'li (str).
    nom/mime: media turini aniqlash uchun.
    caption: story ustiga yoziladigan matn (ixtiyoriy).
    video_uzunlik/en/boy: video story uchun davomiylik(soniya) va o'lchamlar.
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
                duration=int(video_uzunlik), w=en, h=boy, supports_streaming=True,
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


def _shrift(olcham: int):
    """Berilgan o'lchamdagi qalin shrift (truetype bo'lmasa Pillow'ning o'lchamli defaulti)."""
    from PIL import ImageFont
    for yol in (
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(yol, olcham)
        except OSError:
            continue
    try:  # Pillow >= 10.1: o'lchamli default (truetype topilmasa ham katta chiqadi)
        return ImageFont.load_default(size=olcham)
    except TypeError:
        return ImageFont.load_default()


def _satrlarga_bol(chiz, matn, shrift, maks_en):
    """Matnni piksel kengligiga qarab satrlarga bo'ladi."""
    satrlar, joriy = [], ""
    for soz in matn.split():
        sinov = f"{joriy} {soz}".strip()
        quti = chiz.textbbox((0, 0), sinov, font=shrift)
        if quti[2] - quti[0] <= maks_en or not joriy:
            joriy = sinov
        else:
            satrlar.append(joriy)
            joriy = soz
    if joriy:
        satrlar.append(joriy)
    return satrlar


def matnli_rasm(matn: str) -> bytes:
    """Matndan chiroyli, KATTA yozuvli fon-rasm (1080x1920 PNG) yasaydi — matnli story uchun.

    Shrift matn uzunligiga qarab avtomatik moslashadi (qisqa matn — juda katta).
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError as e:
        raise RuntimeError(
            "Matnli story uchun Pillow kerak (pip install pillow), yoki /story ni "
            "rasm/videoga reply qilib ishlating."
        ) from e

    en, boy = 1080, 1920
    maks_en = int(en * 0.86)   # matn kengligi chegarasi
    maks_boy = int(boy * 0.72)  # matn balandligi chegarasi

    # Vertikal gradient fon (to'q ko'k -> siyohrang) — har qatorni chiziq bilan
    rasm = Image.new("RGB", (en, boy))
    chiz = ImageDraw.Draw(rasm)
    yuqori, past = (24, 28, 48), (68, 30, 82)
    for y in range(boy):
        t = y / boy
        r = int(yuqori[0] + (past[0] - yuqori[0]) * t)
        g = int(yuqori[1] + (past[1] - yuqori[1]) * t)
        b = int(yuqori[2] + (past[2] - yuqori[2]) * t)
        chiz.line([(0, y), (en, y)], fill=(r, g, b))

    # Shrift o'lchamini kattadan boshlab, sig'guncha kichraytiramiz
    olcham = 150
    while olcham >= 48:
        shrift = _shrift(olcham)
        satrlar = _satrlarga_bol(chiz, matn, shrift, maks_en)
        qator_h = int(olcham * 1.25)
        if len(satrlar) * qator_h <= maks_boy and all(
            chiz.textbbox((0, 0), s, font=shrift)[2] <= maks_en for s in satrlar
        ):
            break
        olcham -= 10
    else:
        shrift = _shrift(48)
        satrlar = _satrlarga_bol(chiz, matn, shrift, maks_en)
        qator_h = int(48 * 1.25)

    umumiy = len(satrlar) * qator_h
    y = (boy - umumiy) // 2
    for satr in satrlar:
        quti = chiz.textbbox((0, 0), satr, font=shrift)
        w = quti[2] - quti[0]
        x = (en - w) // 2
        # yumshoq soya (o'qilishi uchun)
        chiz.text((x + 4, y + 4), satr, fill=(0, 0, 0), font=shrift)
        chiz.text((x, y), satr, fill=(245, 247, 255), font=shrift)
        y += qator_h

    chiqish = io.BytesIO()
    rasm.save(chiqish, format="PNG")
    return chiqish.getvalue()


async def xabar_yubor(kim: str, matn: str) -> str:
    """Asadbekning shaxsiy akkauntidan boshqa odamga xabar yuboradi.
    kim: @username yoki telefon raqami (+998...) yoki peer nomi.
    matn: yuborilgan xabar matni.
    return: 'OK <username>' yoki xato matni.
    """
    from telethon.errors import (
        UsernameNotOccupiedError, UsernameInvalidError, PeerIdInvalidError,
        FloodWaitError, UserPrivacyRestrictedError,
    )
    client = await _klient()
    hedef = kim.strip()
    # @ ni olib tashla, agar bor bo'lsa
    if hedef.startswith("@"):
        hedef = hedef[1:]
    try:
        entity = await client.get_entity(hedef)
        await client.send_message(entity, matn)
        display = getattr(entity, "username", None) or getattr(entity, "first_name", "") or str(hedef)
        return f"OK @{display}" if getattr(entity, "username", None) else f"OK {display}"
    except (UsernameNotOccupiedError, UsernameInvalidError, PeerIdInvalidError) as e:
        return f"XATO: {hedef} topilmadi ({type(e).__name__})"
    except UserPrivacyRestrictedError:
        return f"XATO: {hedef} — maxfiylik sozlamalari yozishga ruxsat bermayapti"
    except FloodWaitError as e:
        return f"XATO: Telegram vaqtincha to'xtatdi ({e.seconds}s kutish kerak)"
    except Exception as e:
        return f"XATO: {type(e).__name__}: {e}"
