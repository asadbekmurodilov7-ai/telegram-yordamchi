# Telegram yordamchi bot — qadam-baqadam qo'llanma

Bot nima qila oladi:
- ⏰ Eslatmalar: `/eslatma 30d Non olish`, `/eslatma 18:30 Uchrashuv`
- 🌤 Ob-havo: `/obhavo Toshkent`
- 💱 Valyuta kurslari: `/valyuta` (Markaziy bank)
- 📢 Kanal kuzatuvchi: `/kanal kanal_nomi` — kanallardagi yangi qiziq postlarni sizga yuboradi (har soatda tekshiradi, AI qiziqlarini saralaydi)
- 🌅 Har kuni 07:00 da Farg'ona ob-havosini sizga avtomatik yuboradi
- 🤖 AI suhbat: botga yozgan odamlar bilan sizning uslubingizda suhbatlashadi (`/uslub` bilan uslubni sozlaysiz)

Ega buyruqlari (faqat sizga ishlaydi): `/kanal`, `/kanal_ochir`, `/kanallar`, `/uslub`

---

## 1-qadam. BotFather'dan bot oching (2 daqiqa)

1. Telegram'da **@BotFather** ni oching
2. `/newbot` deb yozing
3. Botga nom bering (masalan: *Asadbek Yordamchi*)
4. Username bering — oxiri `bot` bilan tugashi kerak (masalan: `asadbek_yordamchi_bot`)
5. BotFather sizga **token** beradi, shunga o'xshash:
   `7123456789:AAHxK9s...`
   **Bu tokenni hech kimga bermang va saqlab qo'ying!**

## 2-qadam. AI suhbat uchun API kalit (ixtiyoriy)

AI suhbat funksiyasi ishlashi uchun Claude API kaliti kerak:
1. https://console.anthropic.com saytida ro'yxatdan o'ting
2. **API Keys** bo'limidan yangi kalit oching (`sk-ant-...` bilan boshlanadi)
3. Bu pullik xizmat, lekin oddiy foydalanish uchun juda arzon (oyiga bir necha ming so'm atrofida)

Kalit qo'ymasangiz ham bot ishlaydi — faqat AI suhbat o'chiq bo'ladi va kanal postlari saralanmasdan yuboriladi.

## 2.5-qadam. O'zingizni bot egasi qilib belgilash (MUHIM!)

Kunlik ob-havo va kanal xabarlari sizga kelishi uchun bot sizni tanishi kerak:
1. Botni birinchi marta ishga tushirgach, botga `/id` deb yozing
2. Bot chat raqamingizni beradi (masalan: `123456789`)
3. Bu raqamni serverda `ADMIN_CHAT_ID` muhit o'zgaruvchisi sifatida qo'ying va botni qayta ishga tushiring

Shundan keyin:
- Har kuni 07:00 da (Toshkent vaqti) Farg'ona ob-havosi keladi
- `/kanal kunuz` kabi buyruq bilan kanal qo'shsangiz, har soatda yangi qiziq postlar keladi (faqat ochiq kanallar ishlaydi)
- `/uslub` bilan AI qanday gaplashishini sozlaysiz — o'zingiz haqingizda yozing, masalan:
  `/uslub Ismim Asadbek, 20 yoshdaman, Farg'onadanman. Do'stona, hazilkash gaplashaman...`

## 3-qadam. Kompyuterda sinab ko'rish (ixtiyoriy)

Python o'rnatilgan bo'lsa (https://python.org dan yuklab olish mumkin):

```
pip install -r requirements.txt
```

Keyin (Windows PowerShell'da):

```
$env:BOT_TOKEN = "sizning_tokeningiz"
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # ixtiyoriy
python bot.py
```

Telegram'da botingizga `/start` yozing — javob bersa, hammasi ishlayapti!

## 4-qadam. Bepul hostingga qo'yish — Render.com

Bot 24/7 ishlashi uchun serverga qo'yamiz. Eng oson bepul yo'l — **Render**:

1. **GitHub'ga yuklash**
   - https://github.com da account oching
   - Yangi repository yarating (masalan `telegram-bot`)
   - `bot.py` va `requirements.txt` fayllarini yuklang (Add file → Upload files)

2. **Render'da ishga tushirish**
   - https://render.com da GitHub orqali kiring
   - **New → Background Worker** tanlang
   - GitHub repository'ingizni ulang
   - Sozlamalar:
     - Build Command: `pip install -r requirements.txt`
     - Start Command: `python bot.py`
   - **Environment Variables** bo'limida qo'shing:
     - `BOT_TOKEN` = BotFather bergan token
     - `ADMIN_CHAT_ID` = sizning chat raqamingiz (/id buyrug'idan)
     - `ANTHROPIC_API_KEY` = Claude kaliti (bo'lsa)
   - **Deploy** bosing

⚠️ Diqqat: Render'da Background Worker bepul rejada cheklangan bo'lishi mumkin. Agar bepul variant chiqmasa, quyidagi muqobillar bor:
- **PythonAnywhere** (pythonanywhere.com) — bepul, lekin botni har kuni bir marta qayta yoqish kerak
- **Railway** (railway.app) — boshlanishiga bepul kredit beradi
- Eski kompyuter yoki telefonda (Termux orqali) doim yoqiq qoldirish

## 5-qadam. Botni chiroyli qilish (ixtiyoriy)

@BotFather'da:
- `/setdescription` — bot tavsifi
- `/setuserpic` — bot rasmi
- `/setcommands` — buyruqlar menyusi. Shuni yuboring:

```
yordam - Buyruqlar ro'yxati
eslatma - Eslatma qo'shish
eslatmalar - Eslatmalar ro'yxati
obhavo - Ob-havo ma'lumoti
valyuta - Valyuta kurslari
id - Chat raqamini ko'rish
```

---

## Muammo bo'lsa

- Bot javob bermayapti → token to'g'ri qo'yilganini tekshiring
- AI javob bermayapti → `ANTHROPIC_API_KEY` qo'yilganini va hisobda mablag' borligini tekshiring
- Boshqa savol bo'lsa — menga yozing, birga hal qilamiz!
