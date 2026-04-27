"""
handlers/user.py
"""
import json, logging
from aiogram import Router, types, F
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from utils.keyboards import order_action_kb
from database.crud import create_order, get_product, get_all_products
from database.models import Order, User
from config import settings

logger = logging.getLogger(__name__)
router = Router()


def build_webapp_url(products: list) -> str:
    """Mahsulotlarni webapp URL ga qo'shadi"""
    import urllib.parse, os
    prod_list = [
        {"id": p.id, "name": p.name, "price": p.price,
         "category": p.category or "", "photo_url": p.photo_url or ""}
        for p in products if p.is_active
    ]
    # webapp/index.html ga mahsulotlarni yozamiz
    update_webapp_products(prod_list)
    return settings.webapp_url


def update_webapp_products(prod_list: list):
    """webapp/index.html ga mahsulotlar ma'lumotini yozadi"""
    import os
    webapp_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "webapp", "index.html")
    if not os.path.exists(webapp_path):
        return
    try:
        content = open(webapp_path, encoding="utf-8").read()
        marker_start = "// PRODUCTS_DATA_START"
        marker_end = "// PRODUCTS_DATA_END"
        new_data = f"{marker_start}\nconst PRODUCTS_FROM_BOT = {json.dumps(prod_list, ensure_ascii=False)};\n{marker_end}"
        if marker_start in content and marker_end in content:
            import re
            content = re.sub(
                f"{marker_start}.*?{marker_end}",
                new_data,
                content,
                flags=re.DOTALL
            )
        else:
            content = content.replace(
                "// ── PRODUCTS ───",
                new_data + "\n// ── PRODUCTS ───"
            )
        open(webapp_path, "w", encoding="utf-8").write(content)
    except Exception as e:
        logger.error(f"update_webapp_products error: {e}")


@router.message(CommandStart())
async def cmd_start(message: types.Message, db_user, is_new_user: bool, session: AsyncSession):
    from aiogram.types import WebAppInfo
    from aiogram.utils.keyboard import ReplyKeyboardBuilder

    greeting = "👋 Xush kelibsiz" if is_new_user else "👋 Qaytib keldingiz"
    products = await get_all_products(session, only_active=True)
    webapp_url = build_webapp_url(products)

    kb = ReplyKeyboardBuilder()
    kb.button(text="🌐 Buyurtma berish", web_app=WebAppInfo(url=webapp_url))
    kb.adjust(1)

    await message.answer(
        f"{greeting}, <b>{db_user.full_name}</b>!\n\n"
        "🛒 Buyurtma berish uchun tugmani bosing 👇",
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
            items    = data.get("items", [])
            total    = float(data.get("total", 0))
            customer = data.get("customer", {})
            payment  = data.get("payment", "—")

            # Har bir item uchun DB ga yozamiz
            order_ids = []
            for item in items:
                order = await create_order(
                    session,
                    user_id=db_user.telegram_id,
                    product=item.get("name", "—"),
                    quantity=int(item.get("qty", 1)),
                    price=float(item.get("total", 0)),
                    product_id=item.get("id"),
                )
                # Buyurtmaga mijoz ma'lumotlarini qo'shamiz (note sifatida)
                order.note = (
                    f"Ism: {customer.get('name','—')} | "
                    f"Tel: {customer.get('phone','—')} | "
                    f"Manzil: {customer.get('address','—')} | "
                    f"To'lov: {payment}"
                )
                await session.commit()
                order_ids.append(f"#{order.id}")

            # Buyurtma raqami
            order_num = order_ids[0] if order_ids else "#—"

            # Adminlarga xabar
            pay_icon = "⚡ Click" if payment == "click" else "💜 Payme"
            items_text = "\n".join(
                f"  • {i.get('name')} × {i.get('qty')} = {int(i.get('total',0)):,} so'm"
                for i in items
            )
            admin_text = (
                f"🛒 <b>Yangi buyurtma {order_num}</b>\n\n"
                f"👤 {db_user.full_name} (<code>{db_user.telegram_id}</code>)\n"
                f"📦 <b>Mahsulotlar:</b>\n{items_text}\n"
                f"💰 <b>Jami: {int(total):,} so'm</b>\n\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"👤 Ism: {customer.get('name','—')}\n"
                f"📞 Tel: {customer.get('phone','—')}\n"
                f"📍 Manzil: {customer.get('address','—')}\n"
                f"💬 Izoh: {customer.get('note','—')}\n"
                f"💳 To'lov: {pay_icon}"
            )

            for admin_id in settings.admin_list:
                try:
                    await message.bot.send_message(
                        admin_id, admin_text,
                        parse_mode="HTML",
                        reply_markup=order_action_kb(
                            int(order_ids[0].replace("#","")) if order_ids else 0
                        ),
                    )
                except Exception as e:
                    logger.error(f"Admin notify error: {e}")

            await message.answer(
                f"✅ <b>Buyurtma qabul qilindi!</b>\n\n"
                f"🧾 Raqam: <b>{order_num}</b>\n"
                f"💰 Jami: <b>{int(total):,} so'm</b>\n\n"
                f"📞 Tez orada bog'lanamiz, {customer.get('name','')}.  🙏",
                parse_mode="HTML",
            )

        else:
            await message.answer("✅ Qabul qilindi!", parse_mode="HTML")

    except Exception as e:
        logger.error(f"WebApp data error: {e}")
        await message.answer("✅ Buyurtma qabul qilindi!", parse_mode="HTML")


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