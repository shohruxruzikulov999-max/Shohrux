"""
handlers/user.py — foydalanuvchi handlerlari
"""
import logging
import json

from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from utils.keyboards import main_menu_kb, webapp_inline_kb
from database.crud import create_order, get_orders

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message, db_user, is_new_user: bool, session: AsyncSession):
    from config import settings
    greeting = "👋 Xush kelibsiz" if is_new_user else "👋 Qaytib keldingiz"

    await message.answer(
        f"{greeting}, <b>{db_user.full_name}</b>!\n\n"
        f"🤖 Bu botda siz:\n"
        f"• 🌐 WebApp orqali buyurtma berishingiz\n"
        f"• 📦 Buyurtmalaringizni kuzatishingiz\n"
        f"• 👤 Profilingizni ko'rishingiz mumkin.\n\n"
        f"Quyidagi tugmalardan foydalaning 👇",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@router.message(F.text == "ℹ️ Ma'lumot")
async def info_handler(message: types.Message):
    await message.answer(
        "📱 <b>Bot haqida:</b>\n\n"
        "Bu bot <b>aiogram 3.x</b> va <b>Telegram WebApp</b> yordamida qurilgan.\n\n"
        "🔹 <b>Imkoniyatlar:</b>\n"
        "• Interaktiv WebApp interfeysi\n"
        "• Buyurtma qabul qilish tizimi\n"
        "• Admin panel\n"
        "• Foydalanuvchi ma'lumotlar bazasi\n\n"
        "🛠 <b>Stack:</b> aiogram 3 · SQLAlchemy · aiosqlite · pydantic-settings",
        parse_mode="HTML",
        reply_markup=webapp_inline_kb(),
    )


@router.message(F.text == "👤 Profil")
async def profile_handler(message: types.Message, db_user):
    await message.answer(
        f"👤 <b>Profil:</b>\n\n"
        f"🆔 ID: <code>{db_user.telegram_id}</code>\n"
        f"👤 Ism: {db_user.full_name}\n"
        f"🔖 Username: @{db_user.username or '—'}\n"
        f"🌍 Til: {db_user.language_code or '—'}\n"
        f"📅 Ro'yxatdan: {db_user.created_at.strftime('%d.%m.%Y')}\n"
        f"{'🌟 Premium' if db_user.is_premium else ''}",
        parse_mode="HTML",
    )


@router.message(F.text == "🛒 Buyurtmalarim")
async def my_orders_handler(message: types.Message, db_user, session: AsyncSession):
    from sqlalchemy import select
    from database.models import Order

    result = await session.execute(
        select(Order)
        .where(Order.user_id == db_user.telegram_id)
        .order_by(Order.created_at.desc())
        .limit(10)
    )
    orders = result.scalars().all()

    if not orders:
        await message.answer("📭 Hali buyurtmalaringiz yo'q.", parse_mode="HTML")
        return

    status_icons = {"pending": "⏳", "confirmed": "✅", "cancelled": "❌"}
    text = "🛒 <b>Oxirgi buyurtmalaringiz:</b>\n\n"
    for o in orders:
        icon = status_icons.get(o.status, "📦")
        text += (
            f"{icon} #{o.id} — {o.product}\n"
            f"   {o.quantity} dona · {int(o.price):,} so'm\n"
            f"   📅 {o.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        )
    await message.answer(text, parse_mode="HTML")


@router.message(lambda m: m.web_app_data is not None)
async def webapp_data_handler(message: types.Message, db_user, session: AsyncSession):
    """WebApp dan kelgan ma'lumot"""
    raw = message.web_app_data.data
    logger.info(f"WebApp data from {db_user.telegram_id}: {raw}")

    try:
        data = json.loads(raw)
        action = data.get("action", "")

        if action == "order":
            order = await create_order(
                session,
                user_id=db_user.telegram_id,
                product=data.get("product", "Noma'lum"),
                quantity=int(data.get("quantity", 1)),
                price=float(data.get("price", 0)),
            )

            # Admin(lar)ga xabar
            from config import settings
            from utils.keyboards import order_action_kb

            for admin_id in settings.admin_list:
                try:
                    await message.bot.send_message(
                        admin_id,
                        f"🛒 <b>Yangi buyurtma #{order.id}</b>\n\n"
                        f"👤 Foydalanuvchi: {db_user.full_name} "
                        f"(<code>{db_user.telegram_id}</code>)\n"
                        f"📦 Mahsulot: {order.product}\n"
                        f"🔢 Miqdor: {order.quantity}\n"
                        f"💰 Narx: {int(order.price):,} so'm",
                        parse_mode="HTML",
                        reply_markup=order_action_kb(order.id),
                    )
                except Exception:
                    pass

            await message.answer(
                f"✅ <b>Buyurtma #{order.id} qabul qilindi!</b>\n\n"
                f"📦 {order.product} × {order.quantity}\n"
                f"💰 {int(order.price):,} so'm\n\n"
                f"Tez orada bog'lanamiz!",
                parse_mode="HTML",
            )

        elif action == "form":
            await message.answer(
                f"📝 <b>Forma qabul qilindi!</b>\n\n"
                f"👤 {data.get('name', '—')}\n"
                f"📧 {data.get('email', '—')}\n"
                f"💬 {data.get('message', '—')}",
                parse_mode="HTML",
            )
        else:
            await message.answer(
                f"📩 Ma'lumot qabul qilindi:\n<code>{raw}</code>",
                parse_mode="HTML",
            )

    except json.JSONDecodeError:
        await message.answer(f"📩 Qabul qilindi: <code>{raw}</code>", parse_mode="HTML")


@router.callback_query(F.data.startswith("order_"))
async def order_callback(callback: types.CallbackQuery, session: AsyncSession):
    action, order_id = callback.data.split(":")
    order_id = int(order_id)

    from database.crud import update_order_status

    if action == "order_confirm":
        await update_order_status(session, order_id, "confirmed")
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>Tasdiqlandi</b>",
            parse_mode="HTML",
        )
    elif action == "order_cancel":
        await update_order_status(session, order_id, "cancelled")
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ <b>Bekor qilindi</b>",
            parse_mode="HTML",
        )
    await callback.answer()
