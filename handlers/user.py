"""
handlers/user.py
"""
import json, logging
from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from utils.keyboards import main_menu_kb, webapp_inline_kb, products_inline_kb, order_action_kb
from database.models import Order
from database.crud import create_order, get_all_products, get_product

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message, db_user, is_new_user: bool):
    greeting = "👋 Xush kelibsiz" if is_new_user else "👋 Qaytib keldingiz"
    await message.answer(
        f"{greeting}, <b>{db_user.full_name}</b>!\n\n"
        "Quyidagi tugmalardan foydalaning 👇",
        reply_markup=main_menu_kb(), parse_mode="HTML",
    )


@router.message(F.text == "🛍 Mahsulotlar")
async def products_list(message: types.Message, session: AsyncSession):
    prods = await get_all_products(session, only_active=True)
    if not prods:
        await message.answer("📭 Hozircha mahsulotlar yo'q.")
        return
    await message.answer(
        "🛍 <b>Mavjud mahsulotlar:</b>\n\nBirorini tanlang 👇",
        reply_markup=products_inline_kb(prods), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("buy:"))
async def buy_product(callback: types.CallbackQuery, session: AsyncSession, db_user):
    pid = int(callback.data.split(":")[1])
    p = await get_product(session, pid)
    if not p or not p.is_active:
        await callback.answer("❌ Mahsulot mavjud emas", show_alert=True); return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    for qty in [1, 2, 3, 5]:
        b.button(text=f"{qty} ta — {int(p.price*qty):,} so'm",
                 callback_data=f"order:{pid}:{qty}")
    b.button(text="⬅️ Orqaga", callback_data="back_products")
    b.adjust(2, 2, 1)
    await callback.message.edit_text(
        f"{p.emoji} <b>{p.name}</b>\n\n"
        f"💬 {p.description or '—'}\n"
        f"💰 Narx: <b>{int(p.price):,} so'm</b>\n\n"
        "Miqdorni tanlang:",
        reply_markup=b.as_markup(), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("order:"))
async def confirm_order(callback: types.CallbackQuery, session: AsyncSession, db_user):
    _, pid, qty = callback.data.split(":")
    pid, qty = int(pid), int(qty)
    p = await get_product(session, pid)
    if not p:
        await callback.answer("❌ Topilmadi"); return

    order = await create_order(session, db_user.telegram_id, p.name, qty, p.price * qty, p.id)

    from config import settings
    for admin_id in settings.admin_list:
        try:
            await callback.bot.send_message(
                admin_id,
                f"🛒 <b>Yangi buyurtma #{order.id}</b>\n\n"
                f"👤 {db_user.full_name} (<code>{db_user.telegram_id}</code>)\n"
                f"{p.emoji} {p.name} × {qty}\n"
                f"💰 {int(order.price):,} so'm",
                parse_mode="HTML", reply_markup=order_action_kb(order.id),
            )
        except Exception: pass

    await callback.message.edit_text(
        f"✅ <b>Buyurtma #{order.id} qabul qilindi!</b>\n\n"
        f"{p.emoji} {p.name} × {qty}\n"
        f"💰 {int(order.price):,} so'm\n\n"
        "Tez orada bog'lanamiz!", parse_mode="HTML",
    )


@router.callback_query(F.data == "back_products")
async def back_products(callback: types.CallbackQuery, session: AsyncSession):
    prods = await get_all_products(session, only_active=True)
    await callback.message.edit_text(
        "🛍 <b>Mavjud mahsulotlar:</b>\n\nBirorini tanlang 👇",
        reply_markup=products_inline_kb(prods), parse_mode="HTML",
    )


@router.message(F.text == "🛒 Buyurtmalarim")
async def my_orders(message: types.Message, db_user, session: AsyncSession):
    r = await session.execute(
        select(Order).where(Order.user_id == db_user.telegram_id)
        .order_by(Order.created_at.desc()).limit(10)
    )
    orders = r.scalars().all()
    if not orders:
        await message.answer("📭 Hali buyurtmalaringiz yo'q."); return
    icons = {"pending": "⏳", "confirmed": "✅", "cancelled": "❌"}
    text = "🛒 <b>Oxirgi buyurtmalaringiz:</b>\n\n"
    for o in orders:
        text += f"{icons.get(o.status,'📦')} #{o.id} — {o.product} × {o.quantity} | {int(o.price):,} so'm\n"
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "👤 Profil")
async def profile(message: types.Message, db_user):
    await message.answer(
        f"👤 <b>Profil:</b>\n\n"
        f"🆔 ID: <code>{db_user.telegram_id}</code>\n"
        f"👤 Ism: {db_user.full_name}\n"
        f"🔖 Username: @{db_user.username or '—'}\n"
        f"🌍 Til: {db_user.language_code or '—'}\n"
        f"📅 Qo'shilgan: {db_user.created_at.strftime('%d.%m.%Y')}",
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
            order = await create_order(session, db_user.telegram_id, product_name, qty, price, pid)

            from config import settings
            for admin_id in settings.admin_list:
                try:
                    await message.bot.send_message(
                        admin_id,
                        f"🛒 <b>Yangi buyurtma #{order.id}</b>\n"
                        f"👤 {db_user.full_name} (<code>{db_user.telegram_id}</code>)\n"
                        f"📦 {product_name} × {qty} | {int(price):,} so'm",
                        parse_mode="HTML", reply_markup=order_action_kb(order.id),
                    )
                except Exception: pass
            await message.answer(f"✅ Buyurtma #{order.id} qabul qilindi!", parse_mode="HTML")
        else:
            await message.answer(f"📩 Qabul qilindi: <code>{raw}</code>", parse_mode="HTML")
    except Exception:
        await message.answer(f"📩 <code>{raw}</code>", parse_mode="HTML")


@router.callback_query(F.data.startswith("order_"))
async def order_callback(callback: types.CallbackQuery, session: AsyncSession):
    action, oid = callback.data.split(":")
    from database.crud import update_order_status
    status = "confirmed" if action == "order_confirm" else "cancelled"
    await update_order_status(session, int(oid), status)
    label = "✅ Tasdiqlandi" if status == "confirmed" else "❌ Bekor qilindi"
    await callback.message.edit_text(callback.message.text + f"\n\n<b>{label}</b>", parse_mode="HTML")
    await callback.answer()
