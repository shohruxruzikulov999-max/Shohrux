"""
handlers/user.py — faqat /start va WebApp
"""
import json, logging
from aiogram import Router, types, F
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from utils.keyboards import order_action_kb
from database.crud import create_order, get_product, get_all_products
from config import settings

logger = logging.getLogger(__name__)
router = Router()


def build_webapp_url(products: list) -> str:
    """Mahsulotlarni URL ga qo'shib WebApp URL yasaydi"""
    import urllib.parse
    prod_list = [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "category": p.category or "",
            "photo_url": "",  # file_id to'g'ridan URL bo'lmaydi, bo'sh qoladi
        }
        for p in products if p.is_active
    ]
    encoded = urllib.parse.quote(json.dumps(prod_list, ensure_ascii=False))
    return f"{settings.webapp_url}?products={encoded}"


@router.message(CommandStart())
async def cmd_start(message: types.Message, db_user, is_new_user: bool, session: AsyncSession):
    from aiogram.types import InlineKeyboardMarkup, WebAppInfo
    from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

    greeting = "👋 Xush kelibsiz" if is_new_user else "👋 Qaytib keldingiz"

    # Mahsulotlarni DB dan olamiz
    products = await get_all_products(session, only_active=True)
    webapp_url = build_webapp_url(products)

    from aiogram.types import KeyboardButton, WebAppInfo as WI
    kb = ReplyKeyboardBuilder()
    kb.button(text="🌐 Buyurtma berish", web_app=WI(url=webapp_url))
    kb.adjust(1)

    await message.answer(
        f"{greeting}, <b>{db_user.full_name}</b>!\n\n"
        "🌐 Buyurtma berish uchun quyidagi tugmani bosing 👇",
        reply_markup=kb.as_markup(resize_keyboard=True),
        parse_mode="HTML",
    )


@router.message(lambda m: m.web_app_data is not None)
async def webapp_data(message: types.Message, db_user, session: AsyncSession):
    raw = message.web_app_data.data
    try:
        data = json.loads(raw)
        action = data.get("action", "")

        if action == "order":
            pid = data.get("product_id")
            p = await get_product(session, pid) if pid else None
            product_name = p.name if p else data.get("product", "Noma'lum")
            qty = int(data.get("quantity", 1))
            price = float(data.get("price", p.price * qty if p else 0))
            order = await create_order(
                session, db_user.telegram_id, product_name, qty, price, pid
            )
            for admin_id in settings.admin_list:
                try:
                    await message.bot.send_message(
                        admin_id,
                        f"🛒 <b>Yangi buyurtma #{order.id}</b>\n\n"
                        f"👤 {db_user.full_name} (<code>{db_user.telegram_id}</code>)\n"
                        f"📦 {product_name} × {qty}\n"
                        f"💰 {int(price):,} so'm",
                        parse_mode="HTML",
                        reply_markup=order_action_kb(order.id),
                    )
                except Exception:
                    pass
            await message.answer(
                f"✅ <b>Buyurtma #{order.id} qabul qilindi!</b>\n\n"
                f"📦 {product_name} × {qty}\n"
                f"💰 {int(price):,} so'm\n\n"
                "Tez orada bog'lanamiz! 🙏",
                parse_mode="HTML",
            )

        elif action == "form":
            await message.answer(
                f"📝 <b>Xabar qabul qilindi!</b>\n\n"
                f"👤 {data.get('name','—')}\n"
                f"📞 {data.get('phone','—')}\n"
                f"💬 {data.get('message','—')}",
                parse_mode="HTML",
            )
        else:
            await message.answer("✅ Qabul qilindi!", parse_mode="HTML")

    except Exception as e:
        logger.error(f"WebApp data error: {e}")
        await message.answer("✅ Qabul qilindi!", parse_mode="HTML")


@router.callback_query(F.data.startswith("order_"))
async def order_callback(callback: types.CallbackQuery, session: AsyncSession):
    action, oid = callback.data.split(":")
    from database.crud import update_order_status
    status = "confirmed" if action == "order_confirm" else "cancelled"
    await update_order_status(session, int(oid), status)
    label = "✅ Tasdiqlandi" if status == "confirmed" else "❌ Bekor qilindi"
    await callback.message.edit_text(
        callback.message.text + f"\n\n<b>{label}</b>", parse_mode="HTML"
    )
    await callback.answer(label)
