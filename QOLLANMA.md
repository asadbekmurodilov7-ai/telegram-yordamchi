# Nova — to'liq qo'llanma

Bu bot Asadbekning shaxsiy yordamchisi **Nova**. Quyida nima o'zgardi, qayerda va
qanday ishlatilishi to'liq yozilgan.

---

## 1. Nova nima qila oladi

**Yangi imkoniyatlar (shu bosqichda qo'shildi):**
- 📸 **Istorya** — Nova sizning **shaxsiy Telegram profilingizga** story qo'yadi
  (rasm/video yoki matnli).
- 📢 **2 kanalga post** — post/so'rovnoma/dayjest tayyor bo'lganda sizga **tugma**
  bilan keladi; qaysi kanalga joylashni siz tanlaysiz. Faqat siz tasdiqlagan
  (belgilagan) xabar kanalga chiqadi.
- 🧠 **Aqlli qabulxona** — sizdan boshqa odam yozsa, Nova muammoni **o'zi yechishga**
  urinadi; hal qilolmasa yoki narx/kelishuv kabi masala bo'lsa, "Asadbek o'zi
  bog'lanadi" deb sizga xabarni yetkazadi.

**Eski funksiyalar (o'zgarmadi):** eslatmalar, ob-havo, valyuta, kanal kuzatuvchi,
AI dayjest, hujjat/rasm tahlili, ega bilan to'liq AI suhbat.

---

## 2. Har bir o'zgarish qayerda (fayllar)

| Fayl | Nima qilingan |
|------|---------------|
| `bot.py` | `qabulxona_javob()` aqlli yechuvchiga aylantirildi; `/bilim` va `/story` buyruqlari; `tasdiq_callback` (kanal tanlash tugmalari); `KANAL2` sozlamasi; `_tasdiq_klaviatura()` yordamchisi; vaqtli post tanlangan kanalga |
| `story.py` | **yangi** — Telethon userbot orqali profilga story qo'yish (`story_qoy`, `matnli_rasm`) |
| `story_login.py` | **yangi** — bir martalik sessiya (TG_SESSION) olish skripti |
| `requirements.txt` | `telethon` va `pillow` qo'shildi |
| `.env` / `.env.example` | `KANAL2`, `TG_API_ID`, `TG_API_HASH`, `TG_SESSION` kalitlari |

---

## 3. Sozlash — `.env` fayli

`.env` faylidagi kalitlar (buni hech kimga bermang, GitHub'ga yuklamang):

| Kalit | Nima uchun | Qayerdan olinadi |
|-------|-----------|------------------|
| `BOT_TOKEN` | Bot tokeni | @BotFather |
| `ADMIN_CHAT_ID` | Sizning chat raqamingiz | Botga `/id` yozing |
| `GEMINI_API_KEY` | Barcha AI funksiyalar | Google AI Studio |
| `NEWS_KANAL` | 1-kanal (asosiy) | Kanalingiz @username'i |
| `KANAL2` | 2-kanal | 2-kanal @username'i — **bot o'sha kanalda ADMIN bo'lishi shart** |
| `AVTO_NEWS_KANAL` | Avto AI yangiliklar kanali | AI dayjest **tasdiqsiz** shu kanalga o'zi joylanadi (bot admin bo'lsin) |
| `TG_API_ID` | Istorya uchun | my.telegram.org → API development tools |
| `TG_API_HASH` | Istorya uchun | o'sha yerdan |
| `TG_SESSION` | Istorya sessiyasi | `story_login.py` chiqaradi (4-bo'lim) |

> ⚠️ 2 kanalga tanlab post qo'yish uchun `KANAL2` ni to'ldiring. Bo'sh bo'lsa, faqat
> `NEWS_KANAL` tugmasi ko'rinadi.

---

## 4. Istorya sessiyasini olish (bir marta)

Istorya ishlashi uchun sessiya kaliti kerak. Buni **bir marta, o'z kompyuteringizda**
qilasiz:

1. Kutubxonalarni o'rnating: `pip install -r requirements.txt`
2. `.env` da `TG_API_ID` va `TG_API_HASH` borligiga ishonch hosil qiling.
3. Ishga tushiring:
   ```
   python story_login.py
   ```
4. Telefon raqamingizni kiriting (masalan `+99890...`), Telegramga kelgan **kodni**
   kiriting (2 bosqichli parol yoqiq bo'lsa — uni ham).
5. Ekranga uzun **SESSION** satri chiqadi. Uni `.env` da `TG_SESSION=` ga qo'ying.
6. Botni qayta ishga tushiring.

> 🔒 `TG_SESSION` — akkauntingizga kirish kaliti. Uni hech kimga bermang, faqat `.env`
> da saqlang. Chiqib ketsa yoki eskirsa — `story_login.py` ni qayta ishga tushiring.

---

## 5. Buyruqlar qo'llanmasi (faqat siz — ega uchun)

### 📸 Istorya — `/story`
- **Rasm/video bilan:** botga rasm yoki video yuboring, o'sha xabarga **reply** qilib
  `/story Bugungi kun ajoyib!` yozing (matn — story ustidagi yozuv, ixtiyoriy).
- **Matnli story:** `/story Salom, bugun yangi dars bor!` — Nova matndan chiroyli
  fon-rasm yasab, story qo'yadi.
- Story shaxsiy profilingizga 24 soatga joylanadi.

### 🎵 Musiqali istorya — `/musiqa`
`/musiqa <qo'shiq nomi>` — bot qo'shiqni YouTube'dan topadi, uning **eng "rekli"
(eng ko'p qayta ko'rilgan) qismini** ajratadi va rasm+musiqadan video istorya yasab,
profilingizga joylaydi. Rasm ustiga qo'yish uchun rasmga **reply** qilib `/musiqa
<qo'shiq>` yozing; rasmsiz bo'lsa qo'shiq nomi fon qilib chiqadi. Menyudagi
**🎵 Musiqali story** tugmasi ham shu ishni qiladi.

### 🧠 Bilim bazasi — `/bilim`
Nova mijozlarga to'g'ri javob berishi uchun xizmatlaringiz/narx/FAQ'ni kiriting:
```
/bilim Men veb-sayt va Telegram bot yasayman. Narx loyihaga qarab kelishiladi.
Ish vaqti 9:00-18:00. Bepul konsultatsiya bor.
```
`/bilim` (matnsiz) — hozirgi saqlangan ma'lumotni ko'rsatadi.

### 📢 Kanalga post — tugma bilan
1. Nova bilan suhbatda "kanalimga shu haqida yoz" yoki "so'rovnoma qo'y" deng.
2. Nova post/so'rovnoma matnini tayyorlab, pastida tugmalar bilan yuboradi:
   `📢 @kanal1` · `📰 @kanal2` · `❌ Bekor`.
3. Kerakli kanal tugmasini bosing — faqat o'sha kanalga joylanadi.
4. Vaqt aytilgan bo'lsa (masalan "ertaga 9 da"), o'sha vaqtda tanlangan kanalga joylanadi.

Xuddi shu tugmalar kanal-kuzatuvchi dayjesti uchun ham chiqadi.

### 📰 Avto yangiliklar kanali (`AVTO_NEWS_KANAL`)
`AVTO_NEWS_KANAL` sozlangan bo'lsa (masalan `@ainews_uzz`), AI dayjest kuniga 3 mahal
(09:00, 14:00, 20:00) **tasdiqsiz, avtomatik** o'sha kanalga joylanadi — sizdan
so'ramaydi. `/dayjest` bilan qo'lda ham chaqirsangiz o'sha kanalga ketadi. Bu kanalda
ham bot admin bo'lishi shart.

---

## 6. Qabulxona qanday ishlaydi (sizdan boshqa odam yozsa)

1. **Birinchi xabar:** Nova tanishadi — "Men Asadbekning yordamchisi Nova'man,
   muammoingizni yozing."
2. **Muammo/savol:** Nova AI bilan (kerak bo'lsa internetdan qidirib) **o'zi javob
   berishga** urinadi. `/bilim` dagi ma'lumotdan foydalanadi.
3. **Hal qildi** → mijozga javob beradi; sizga `ℹ️ Nova javob berdi` deb qisqa xabar keladi.
4. **Hal qilolmadi** (narx/to'lov/hamkorlik/uchrashuv/shaxsiy kelishuv yoki aniq
   bilmasa) → mijozga "Asadbek band, bo'shashi bilan o'zi bog'lanadi" deydi **va**
   sizga `⚠️ YECHILMADI — SIZ BOG'LANING` tagi bilan odamning ismi/username va savoli
   yuboriladi.

---

## 7. Ishga tushirish va deploy

**Lokal (kompyuterda):**
```
pip install -r requirements.txt
python bot.py
```

**Serverda (Render / Railway / Fly):** loyihada `Dockerfile`, `fly.toml`,
`railway.json` bor. Deploy qilishda **Environment Variables** ga barcha `.env`
kalitlarini qo'shing — jumladan yangi: `KANAL2`, `TG_API_ID`, `TG_API_HASH`,
`TG_SESSION`. `TG_SESSION` ni avval lokalda (4-bo'lim) olib, keyin serverga qo'ying.

> Serverda bot admin bo'lgan kanallargagina post qila oladi — `NEWS_KANAL` va
> `KANAL2` da botni admin qiling.

---

## 8. Muammolar (troubleshooting)

- **Kanalga joylanmadi** → bot o'sha kanalda **admin** emas. Kanal sozlamalari →
  Administrators → botni qo'shing (post yuborish huquqi bilan).
- **Istorya chiqmadi / "sozlanmagan"** → `.env` da `TG_API_ID`, `TG_API_HASH`,
  `TG_SESSION` borligini tekshiring. Sessiya eskirgan bo'lsa `story_login.py` ni
  qayta ishga tushiring.
- **Matnli `/story` xato berdi** → Pillow o'rnatilmagan bo'lishi mumkin:
  `pip install pillow`. Yoki rasm/videoga reply qilib ishlating.
- **Nova javob bermayapti / qabulxona ishlamayapti** → `GEMINI_API_KEY` to'g'ri
  qo'yilganini tekshiring.
- **2-kanal tugmasi ko'rinmayapti** → `.env` da `KANAL2` bo'sh. To'ldiring va botni
  qayta ishga tushiring.
