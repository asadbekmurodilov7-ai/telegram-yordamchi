"""Bir martalik skript: Telegram (Telethon) sessiya satrini olish.

Buni FAQAT bir marta, o'z kompyuteringizda ishga tushiring:

    python story_login.py

Dastur telefon raqamingizni so'raydi, Telegramga kelgan kodni (va agar yoqilgan
bo'lsa 2 bosqichli parolni) kiritasiz. So'ng ekranga uzun bir satr — SESSION
chiqadi. O'sha satrni .env faylida TG_SESSION= ga qo'ying.

MUHIM: SESSION satri sizning akkauntingizga kirish kaliti — uni hech kimga bermang,
git'ga qo'ymang, faqat .env (maxfiy) faylda saqlang.
"""

import os

from dotenv import load_dotenv

load_dotenv()

try:
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    raise SystemExit("Avval Telethon o'rnating:  pip install telethon")


def _sora(nom, env_kalit):
    qiymat = os.environ.get(env_kalit, "").strip()
    return qiymat or input(f"{nom}: ").strip()


def main():
    api_id = int(_sora("TG_API_ID (my.telegram.org)", "TG_API_ID"))
    api_hash = _sora("TG_API_HASH", "TG_API_HASH")

    print("\nTelegramga kirish... telefon raqam (masalan +99890...) va kod so'raladi.\n")
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_satri = client.session.save()
        me = client.get_me()
        print("\n" + "=" * 60)
        print(f"Kirdingiz: {me.first_name} (@{me.username})" if me else "Kirdingiz.")
        print("Quyidagi satrni .env faylida TG_SESSION= ga qo'ying (bir qatorda):\n")
        print(session_satri)
        print("=" * 60)
        print("\nBu satrni hech kimga bermang!")


if __name__ == "__main__":
    main()
