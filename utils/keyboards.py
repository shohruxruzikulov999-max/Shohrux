from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from config import settings

def main_menu_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🌐 WebApp", web_app=WebAppInfo(url=settings.webapp_url))
    kb.button(text="🛒 Buyurtmalarim")
    kb.button(text="🛍 Mahsulotlar")
    kb.button(text="👤 Profil")
    kb.adjust(1, 2, 1)
    return kb.as_markup(resize_keyboard=True)

def admin_menu_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📊 Statistika")
    kb.button(text="👥 Foydalanuvchilar")
    kb.button(text="📦 Buyurtmalar")
    kb.button(text="🛍 Mahsulotlar")
    kb.button(text="📢 Broadcast")
    kb.button(text="🔙 Orqaga")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup(resize_keyboard=True)

def cancel_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="❌ Bekor qilish")
    return kb.as_markup(resize_keyboard=True)

def webapp_inline_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🚀 WebApp ochish", web_app=WebAppInfo(url=settings.webapp_url))
    return b.as_markup()

def order_action_kb(order_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data=f"order_confirm:{order_id}")
    b.button(text="❌ Bekor",      callback_data=f"order_cancel:{order_id}")
    b.adjust(2)
    return b.as_markup()

def products_inline_kb(products):
    b = InlineKeyboardBuilder()
    for p in products:
        b.button(text=f"{p.emoji} {p.name} — {int(p.price):,} so'm",
                 callback_data=f"buy:{p.id}")
    b.adjust(1)
    return b.as_markup()

def product_manage_kb(product_id: int, is_active: bool):
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Tahrirlash",  callback_data=f"prod_edit:{product_id}")
    b.button(text="🗑 O'chirish",   callback_data=f"prod_del:{product_id}")
    b.button(text="🟢 Yoqish" if not is_active else "🔴 O'chirish",
             callback_data=f"prod_toggle:{product_id}")
    b.adjust(2, 1)
    return b.as_markup()
