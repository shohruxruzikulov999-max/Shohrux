# 🤖 Aiogram WebApp Bot — To'liq Shablon v2

Production-ready Telegram bot shabloni: aiogram 3, SQLAlchemy, WebApp, Static Admin Panel.

## 📁 Fayl tuzilmasi

```
tgbot_template/
├── bot.py                   ← Asosiy kirish nuqtasi
├── config.py                ← Pydantic Settings (.env o'qish)
├── requirements.txt
├── .env.example             ← Namuna .env fayl
│
├── database/
│   ├── models.py            ← User, Product, Order, BroadcastLog
│   └── crud.py              ← Barcha async CRUD operatsiyalar
│
├── handlers/
│   ├── user.py              ← Start, mahsulotlar, buyurtma, WebApp
│   └── admin.py             ← Statistika, mahsulot CRUD (FSM), broadcast, ban
│
├── middlewares/
│   └── middlewares.py       ← DB, Ban, Admin middleware
│
├── utils/
│   ├── filters.py           ← IsAdmin filter
│   └── keyboards.py         ← Barcha klaviaturalar
│
├── webapp/
│   └── index.html           ← Telegram WebApp (buyurtma, forma, info)
│
└── admin/
    └── index.html           ← Static admin panel
```

## ⚙️ O'rnatish

```bash
cp .env.example .env        # Sozlang
pip install -r requirements.txt
python bot.py
```

## 🛍 Mahsulot boshqaruvi

### Bot orqali (admin):
- `🛍 Mahsulotlar` → mahsulotlar ro'yxati
- Har bir mahsulotda: **tahrirlash / o'chirish / yoqish-o'chirish** tugmalari
- `➕ Yangi mahsulot` — FSM bilan bosqichma-bosqich qo'shish

### Admin panel orqali:
- Mahsulot qo'shish modali (nom, narx, emoji, kategoriya, tavsif)
- Tahrirlash modali
- O'chirish (tasdiqlash bilan)
- Faol/nofaol almashtirish

## 🤖 Bot komandalar

| Komanda     | Kim    | Tavsif                    |
|-------------|--------|---------------------------|
| `/start`    | Hamma  | Boshlash                  |
| `/admin`    | Admin  | Admin menyusi             |
| `/ban <id>` | Admin  | Bloklash                  |
| `/unban <id>`| Admin | Blokni ochish             |

## 🔐 Admin panel

- URL: `admin/index.html`
- Default parol: **`admin123`**
- Mahsulot CRUD, foydalanuvchilar, buyurtmalar, broadcast, .env

## 🌐 Hosting

| Qism        | Servis         | Narx    |
|-------------|----------------|---------|
| Bot (Python)| Railway.app    | Bepul   |
| WebApp+Admin| GitHub Pages   | Bepul   |
