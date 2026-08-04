"""Musiqali istorya — qo'shiq nomidan topib, uning eng "rekli" (YouTube'da eng ko'p
qayta ko'rilgan) qismini ajratib, rasm + audio'dan video story yasaydi.

Bosqichlar:
  1. yt-dlp qo'shiqni YouTube'dan qidiradi va ma'lumotini (heatmap bilan) oladi
  2. heatmap'dan eng ko'p qayta ko'rilgan (eng rekli) segment tanlanadi
     (boshidagi doimo baland "intro" chetlab o'tiladi)
  3. bestaudio yuklab olinadi, ffmpeg o'sha segmentni kesib, rasm ustiga qo'yib
     vertikal (1080x1920) mp4 video yasaydi
  4. video story sifatida joylanadi

Kerak: yt-dlp (pip), ffmpeg (tizimda o'rnatilgan bo'lishi shart).
"""

import logging
import os
import shutil
import subprocess
import tempfile

log = logging.getLogger("musiqa")

FFMPEG = os.environ.get("FFMPEG_YOLI", "ffmpeg")
COOKIE_FAYL = os.path.join(os.path.dirname(__file__), "www.youtube.com_cookies.txt")
EN, BOY = 1080, 1920


def _segment_boshi(info: dict, klip: int) -> float:
    """Heatmap'dan eng rekli segment boshini (soniya) tanlaydi.

    Boshidagi ~15s (har doim eng baland "intro") va oxiri chetlab o'tiladi.
    """
    dur = info.get("duration") or 0
    hm = info.get("heatmap") or []
    if hm and dur:
        nomzod = [h for h in hm if h.get("start_time", 0) >= 15
                  and h.get("end_time", 0) <= dur - 5] or hm
        top = max(nomzod, key=lambda h: h.get("value", 0))
        boshi = max(0.0, float(top.get("start_time", 0)) - 3)  # chorusdan biroz oldin
    else:
        boshi = dur * 0.3 if dur else 0.0
    if dur:
        boshi = min(boshi, max(0.0, dur - klip))
    return float(boshi)


def _qidiruv_natijalari(yt_dlp, base_opts: dict, nom: str, soni: int = 6) -> list:
    """Qo'shiq nomi bo'yicha YouTube'dan bir nechta nomzodni qaytaradi (yuklamasdan).

    Avval oddiy qidiruv, natija bo'lmasa 'audio' qo'shib qayta uriniladi — Uzbek
    ijrochilar (masalan 'Jahongir Otajonov') ko'pincha shunda topiladi.
    """
    search_opts = {
        **base_opts,
        "default_search": f"ytsearch{soni}",
        "skip_download": True,
        "extract_flat": "in_playlist",
    }
    for sorov in (nom, f"{nom} audio", f"{nom} qo'shiq"):
        try:
            with yt_dlp.YoutubeDL(search_opts) as y:
                res = y.extract_info(sorov, download=False)
        except Exception as e:  # qidiruvning o'zi uzilsa — keyingi so'rovga o'tamiz
            log.warning("Qidiruv xatosi ('%s'): %s", sorov, e)
            continue
        entries = [e for e in (res.get("entries") or [res]) if e]
        if entries:
            return entries
    return []


def musiqali_video(nom: str, rasm_bytes: bytes | None = None,
                   matn: str | None = None, klip: int = 25):
    """Qo'shiqni topib, eng rekli qismidan rasm ustiga qo'yilgan video yasaydi.

    nom: qo'shiq nomi (qidiruv so'rovi).
    rasm_bytes: fon rasmi (bo'lmasa — qo'shiq sarlavhasidan matnli fon yasaladi).
    Qaytaradi: (video_bytes, sarlavha, klip_uzunlik).
    """
    import yt_dlp

    tmp = tempfile.mkdtemp(prefix="story_musiqa_")
    try:
        base_opts = {
            "quiet": True, "no_warnings": True, "noplaylist": True,
            "geo_bypass": True,
        }
        if os.path.exists(COOKIE_FAYL):
            base_opts["cookiefile"] = COOKIE_FAYL

        # 1) Bir nechta nomzodni topamiz (yuklamasdan)
        nomzodlar = _qidiruv_natijalari(yt_dlp, base_opts, nom)
        if not nomzodlar:
            raise RuntimeError(
                f"'{nom}' bo'yicha YouTube'dan hech narsa topilmadi. "
                "Qo'shiq nomini ijrochi bilan birga aniqroq yozib ko'ring."
            )

        # 2) Nomzodlarni navbat bilan yuklab ko'ramiz — birinchi ishlaganida to'xtaymiz
        dl_opts = {
            **base_opts, "format": "bestaudio/best",
            "outtmpl": os.path.join(tmp, "audio.%(ext)s"),
        }
        info, audio_yol, oxirgi_xato = None, None, None
        for nomzod in nomzodlar[:5]:
            url = (nomzod.get("webpage_url") or nomzod.get("url")
                   or nomzod.get("id"))
            if not url:
                continue
            try:
                for f in os.listdir(tmp):  # oldingi urinish qoldig'ini tozalaymiz
                    if f.startswith("audio."):
                        os.remove(os.path.join(tmp, f))
                with yt_dlp.YoutubeDL(dl_opts) as y:
                    info = y.extract_info(url, download=True)
                    if "entries" in info:
                        info = info["entries"][0]
                    audio_yol = y.prepare_filename(info)
                if not os.path.exists(audio_yol):
                    fayllar = [os.path.join(tmp, f) for f in os.listdir(tmp)
                               if f.startswith("audio.")]
                    audio_yol = fayllar[0] if fayllar else None
                if audio_yol and os.path.exists(audio_yol):
                    break
            except Exception as e:
                oxirgi_xato = e
                log.warning("Nomzodni yuklab bo'lmadi (%s): %s", url, e)
                info, audio_yol = None, None
                continue

        if not info or not audio_yol or not os.path.exists(audio_yol):
            raise RuntimeError(
                f"'{nom}' topildi, lekin audiosini yuklab bo'lmadi"
                + (f": {oxirgi_xato}" if oxirgi_xato else ".")
            )

        sarlavha = info.get("title") or nom
        boshi = _segment_boshi(info, klip)

        # Fon rasmi
        if rasm_bytes is None:
            import story
            rasm_bytes = story.matnli_rasm(matn or sarlavha)
        rasm_yol = os.path.join(tmp, "fon.png")
        with open(rasm_yol, "wb") as f:
            f.write(rasm_bytes)

        chiqish = os.path.join(tmp, "story.mp4")
        cmd = [
            FFMPEG, "-y",
            "-loop", "1", "-framerate", "30", "-i", rasm_yol,
            "-ss", f"{boshi:.2f}", "-t", str(klip), "-i", audio_yol,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={EN}:{BOY}:force_original_aspect_ratio=increase,"
                   f"crop={EN}:{BOY}",
            "-r", "30",
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(klip), "-shortest",
            chiqish,
        ]
        natija = subprocess.run(cmd, capture_output=True)
        if natija.returncode != 0 or not os.path.exists(chiqish):
            xato = natija.stderr.decode("utf-8", "ignore")[-500:]
            raise RuntimeError(f"ffmpeg xatosi: {xato}")

        with open(chiqish, "rb") as f:
            video = f.read()
        return video, sarlavha, klip
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
