"""
handlers/admin.py
"""
import asyncio, logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from utils.filters import IsAdmin
from utils.keyboards import admin_menu_kb, main_menu_kb, cancel_kb, product_manage_kb
from utils.excel import orders_to_excel
from database.crud import (
    get_user_count, get_order_count, get_total_revenue,
    get_all_users, get_active_user_ids, get_orders, get_broadcasts,
    ban_user, unban_user, save_broadcast,
    get_all_products, get_product, create_product, update_product,
    delete_product, toggle_product, update_order_status,
)

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())


# ── FSM States ──────────────────────────────────────────────────────────────

class ProductAdd(StatesGroup):
    name     = State()
    price    = State()
    photo    = State()
    category = State()
    desc     = State()

class ProductEdit(StatesGroup):
    field = State()
    value = State()

class BroadcastSt(StatesGroup):
    text    = State()
    confirm = State()


# ── /admin ──────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("⚙️ <b>Admin panel</b>", reply_markup=admin_menu_kb(), parse_mode="HTML")


@router.message(F.text == "🔙 Orqaga")
async def back_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Asosiy menyu", reply_markup=main_menu_kb())


# ── Excel ────────────────────────────────────────────────────────────────────

@router.message(Command("excel"))
async def export_excel(message: types.Message, session: AsyncSession):
    await message.answer("⏳ Excel fayl tayyorlanmoqda...")
    orders = await get_orders(session, limit=10000)
    if not orders:
        await message.answer("📭 Hali buyurtmalar yo'q."); return
    try:
        excel_bytes = orders_to_excel(orders)
        from aiogram.types import BufferedInputFile
        import datetime
        filename = f"buyurtmalar_{datetime.datetime.now().strftime('%d-%m-%Y')}.xlsx"
        await message.answer_document(
            BufferedInputFile(excel_bytes, filename=filename),
            caption=(
                f"📊 <b>Buyurtmalar ro'yxati</b>\n\n"
                f"📦 Jami: <b>{len(orders)}</b> ta\n"
                f"✅ Tasdiqlangan: <b>{sum(1 for o in orders if o.status=='confirmed')}</b> ta\n"
                f"⏳ Kutmoqda: <b>{sum(1 for o in orders if o.status=='pending')}</b> ta\n"
                f"❌ Bekor: <b>{sum(1 for o in orders if o.status=='cancelled')}</b> ta"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")


@router.message(F.text == "📥 Excel yuklab olish")
async def excel_btn(message: types.Message, session: AsyncSession):
    await export_excel(message, session)


# ── Statistika ───────────────────────────────────────────────────────────────

@router.message(F.text == "📊 Statistika")
async def stats(message: types.Message, session: AsyncSession):
    users   = await get_user_count(session)
    orders  = await get_order_count(session)
    revenue = await get_total_revenue(session)
    prods   = await get_all_products(session)
    bcs     = await get_broadcasts(session, limit=1000)
    await message.answer(
        f"📊 <b>Bot statistikasi</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users}</b>\n"
        f"🛍 Mahsulotlar: <b>{len(prods)}</b> ta\n"
        f"📦 Buyurtmalar: <b>{orders}</b>\n"
        f"💰 Tushumlar: <b>{int(revenue):,} so'm</b>\n"
        f"📢 Broadcastlar: <b>{len(bcs)}</b>",
        parse_mode="HTML",
    )


# ── Foydalanuvchilar ─────────────────────────────────────────────────────────

@router.message(F.text == "👥 Foydalanuvchilar")
async def users_list(message: types.Message, session: AsyncSession):
    users = await get_all_users(session, limit=30)
    total = await get_user_count(session)
    text = f"👥 <b>So'nggi 30 ({total} jami):</b>\n\n"
    for u in users:
        icon = "🚫" if u.is_banned else "✅"
        text += f"{icon} {u.full_name} | <code>{u.telegram_id}</code>\n"
    await message.answer(text[:4096], parse_mode="HTML")


@router.message(Command("ban"))
async def ban_cmd(message: types.Message, session: AsyncSession):
    args = message.text.split()
    if len(args) < 2: await message.answer("❗ /ban <id>"); return
    try:
        ok = await ban_user(session, int(args[1]))
        await message.answer(f"{'🚫 Bloklandi' if ok else '❌ Topilmadi'}: <code>{args[1]}</code>", parse_mode="HTML")
    except ValueError:
        await message.answer("❗ ID raqam bo'lishi kerak")


@router.message(Command("unban"))
async def unban_cmd(message: types.Message, session: AsyncSession):
    args = message.text.split()
    if len(args) < 2: await message.answer("❗ /unban <id>"); return
    try:
        ok = await unban_user(session, int(args[1]))
        await message.answer(f"{'✅ Blok ochildi' if ok else '❌ Topilmadi'}: <code>{args[1]}</code>", parse_mode="HTML")
    except ValueError:
        await message.answer("❗ ID raqam bo'lishi kerak")


# ── Buyurtmalar ──────────────────────────────────────────────────────────────

@router.message(F.text == "📦 Buyurtmalar")
async def orders_list(message: types.Message, session: AsyncSession):
    orders = await get_orders(session, limit=20)
    if not orders:
        await message.answer("📭 Buyurtmalar yo'q."); return
    icons = {"pending":"⏳","confirmed":"✅","cancelled":"❌"}
    text = f"📦 <b>Oxirgi {len(orders)} buyurtma:</b>\n\n"
    for o in orders:
        text += f"{icons.get(o.status,'📦')} #{o.id} | <code>{o.user_id}</code> | {o.product} x{o.quantity} = {int(o.price):,} so'm\n"
    await message.answer(text[:4096], parse_mode="HTML")


# ── Mahsulotlar ──────────────────────────────────────────────────────────────

@router.message(F.text == "🛍 Mahsulotlar")
async def products_admin(message: types.Message, session: AsyncSession):
    prods = await get_all_products(session)
    b = InlineKeyboardBuilder()
    for p in prods:
        status = "🟢" if p.is_active else "🔴"
        photo  = "🖼" if p.photo_url else "📦"
        b.button(text=f"{status} {photo} {p.name} — {int(p.price):,}",
                 callback_data=f"padmin:{p.id}")
    b.button(text="➕ Yangi mahsulot qo'shish", callback_data="prod_new")
    b.adjust(1)
    await message.answer(
        f"🛍 <b>Mahsulotlar ({len(prods)} ta):</b>\n\n"
        "🟢 Faol  |  🔴 Nofaol  |  🖼 Rasmi bor  |  📦 Rasmsiz",
        reply_markup=b.as_markup(), parse_mode="HTML",
    )


# ── Mahsulot detail ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("padmin:"))
async def product_detail(callback: types.CallbackQuery, session: AsyncSession):
    pid = int(callback.data.split(":")[1])
    p = await get_product(session, pid)
    if not p: await callback.answer("Topilmadi"); return
    status = "🟢 Faol" if p.is_active else "🔴 Nofaol"
    text = (
        f"📦 <b>{p.name}</b>\n\n"
        f"📝 {p.description or '—'}\n"
        f"💰 {int(p.price):,} so'm\n"
        f"🗂 {p.category or '—'}\n"
        f"📌 {status} | ID: {p.id}\n"
        f"🖼 {'Rasm bor' if p.photo_url else 'Rasm yo\'q'}"
    )
    kb = product_manage_kb(p.id, p.is_active)
    if p.photo_url:
        try:
            await callback.message.answer_photo(p.photo_url, caption=text, parse_mode="HTML", reply_markup=kb)
            await callback.message.delete()
        except Exception:
            await callback.message.edit_text(text + f"\n🔗 {p.photo_url}", reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ── Yangi mahsulot (FSM) ─────────────────────────────────────────────────────

@router.callback_query(F.data == "prod_new")
async def prod_new_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ProductAdd.name)
    await callback.message.answer(
        "➕ <b>Yangi mahsulot qo'shish</b>\n\n1/5 — Nomini kiriting:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )
    await callback.answer()


@router.message(ProductAdd.name)
async def prod_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("❌", reply_markup=admin_menu_kb()); return
    await state.update_data(name=message.text)
    await state.set_state(ProductAdd.price)
    await message.answer("2/5 — Narxini kiriting (so'mda, faqat raqam):")


@router.message(ProductAdd.price)
async def prod_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("❌", reply_markup=admin_menu_kb()); return
    try:
        price = float(message.text.replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("❗ Faqat raqam kiriting:"); return
    await state.update_data(price=price)
    await state.set_state(ProductAdd.photo)
    await message.answer(
        "3/5 — Rasm URL sini yuboring 🖼\n\n"
        "Rasmni <b>imgbb.com</b> ga yuklang va <b>Direct link</b> ni yuboring.\n"
        "Rasm yo'q bo'lsa <b>yoq</b> deb yozing.",
        parse_mode="HTML"
    )


@router.message(ProductAdd.photo)
async def prod_photo(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("❌", reply_markup=admin_menu_kb()); return

    photo_url = None
    if message.text and message.text.lower() not in ("yoq", "yo'q", "-", "skip"):
        url = message.text.strip()
        # URL tekshirish
        if url.startswith("http"):
            photo_url = url
        else:
            await message.answer("❗ To'g'ri URL kiriting (http... bilan boshlanishi kerak) yoki yoq deb yozing:")
            return

    await state.update_data(photo_url=photo_url)
    await state.set_state(ProductAdd.category)
    await message.answer("4/5 — Kategoriyani kiriting (masalan: Ovqat, Ichimlik, Shirinlik):")


@router.message(ProductAdd.category)
async def prod_category(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("❌", reply_markup=admin_menu_kb()); return
    await state.update_data(category=message.text.strip())
    await state.set_state(ProductAdd.desc)
    await message.answer("5/5 — Tavsifni kiriting (yoki yoq deb yozing):")


@router.message(ProductAdd.desc)
async def prod_desc_finish(message: types.Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("❌", reply_markup=admin_menu_kb()); return
    data = await state.get_data()
    desc = "" if message.text.lower() in ("yo'q", "yoq", "-") else message.text
    p = await create_product(
        session,
        name=data["name"], price=data["price"],
        photo_url=data.get("photo_url"),
        category=data["category"], description=desc,
    )
    await state.clear()
    text = (
        f"✅ <b>Mahsulot qo'shildi!</b>\n\n"
        f"📦 <b>{p.name}</b>\n"
        f"💰 {int(p.price):,} so'm\n"
        f"🗂 {p.category}\n"
        f"🖼 {'Rasm bor ✅' if p.photo_url else 'Rasmsiz'}"
    )
    if p.photo_url:
        try:
            await message.answer_photo(p.photo_url, caption=text, parse_mode="HTML", reply_markup=admin_menu_kb())
        except Exception:
            await message.answer(text + f"\n\n⚠️ Rasm yuklanmadi — URL ni tekshiring", reply_markup=admin_menu_kb(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=admin_menu_kb(), parse_mode="HTML")


# ── Tahrirlash (FSM) ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("prod_edit:"))
async def prod_edit_start(callback: types.CallbackQuery, state: FSMContext):
    pid = int(callback.data.split(":")[1])
    await state.update_data(edit_pid=pid)
    await state.set_state(ProductEdit.field)
    b = InlineKeyboardBuilder()
    for label, key in [("📛 Nom","name"),("💰 Narx","price"),("🖼 Rasm URL","photo_url"),("🗂 Kategoriya","category"),("📝 Tavsif","description")]:
        b.button(text=label, callback_data=f"editf:{key}")
    b.button(text="❌ Bekor", callback_data="edit_cancel")
    b.adjust(2, 2, 1)
    await callback.message.answer("✏️ Qaysi maydonni tahrirlaysiz?", reply_markup=b.as_markup())
    await callback.answer()


@router.callback_query(F.data == "edit_cancel")
async def edit_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear(); await callback.message.delete(); await callback.answer("Bekor")


@router.callback_query(F.data.startswith("editf:"), ProductEdit.field)
async def prod_edit_field(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    await state.update_data(edit_field=field)
    await state.set_state(ProductEdit.value)
    labels = {"name":"yangi nom","price":"yangi narx (raqam)","photo_url":"yangi rasm URL (http...)","category":"yangi kategoriya","description":"yangi tavsif"}
    await callback.message.answer(f"✏️ {labels.get(field,'yangi qiymat')} kiriting:")
    await callback.answer()


@router.message(ProductEdit.value)
async def prod_edit_value(message: types.Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    pid, field = data["edit_pid"], data["edit_field"]
    value = message.text
    if field == "price":
        try: value = float(value.replace(" ","").replace(",","."))
        except ValueError: await message.answer("❗ Faqat raqam:"); return
    elif field == "photo_url":
        if not value.startswith("http"):
            await message.answer("❗ URL http... bilan boshlanishi kerak:"); return
    await update_product(session, pid, **{field: value})
    await state.clear()
    p = await get_product(session, pid)
    await message.answer(
        f"✅ <b>Yangilandi!</b>\n\n📦 <b>{p.name}</b> — {int(p.price):,} so'm",
        reply_markup=admin_menu_kb(), parse_mode="HTML",
    )


# ── O'chirish ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("prod_del:"))
async def prod_del_confirm(callback: types.CallbackQuery):
    pid = callback.data.split(":")[1]
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, o'chirish", callback_data=f"prod_del_ok:{pid}")
    b.button(text="❌ Bekor", callback_data=f"padmin:{pid}")
    b.adjust(2)
    await callback.message.answer("⚠️ O'chirishni tasdiqlaysizmi?", reply_markup=b.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("prod_del_ok:"))
async def prod_del_exec(callback: types.CallbackQuery, session: AsyncSession):
    pid = int(callback.data.split(":")[1])
    ok = await delete_product(session, pid)
    await callback.message.edit_text("✅ O'chirildi." if ok else "❌ Topilmadi.")
    await callback.answer()


# ── Toggle ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("prod_toggle:"))
async def prod_toggle(callback: types.CallbackQuery, session: AsyncSession):
    pid = int(callback.data.split(":")[1])
    new_state = await toggle_product(session, pid)
    if new_state is None: await callback.answer("Topilmadi"); return
    await callback.answer("🟢 Yoqildi" if new_state else "🔴 O'chirildi", show_alert=True)
    p = await get_product(session, pid)
    status = "🟢 Faol" if p.is_active else "🔴 Nofaol"
    text = f"📦 <b>{p.name}</b>\n\n📝 {p.description or '—'}\n💰 {int(p.price):,} so'm\n🗂 {p.category or '—'}\n📌 {status}"
    kb = product_manage_kb(p.id, p.is_active)
    if p.photo_url:
        try:
            await callback.message.answer_photo(p.photo_url, caption=text, parse_mode="HTML", reply_markup=kb)
            await callback.message.delete()
        except Exception:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ── Broadcast ────────────────────────────────────────────────────────────────

@router.message(F.text == "📢 Broadcast")
async def bc_start(message: types.Message, state: FSMContext):
    await state.set_state(BroadcastSt.text)
    await message.answer("✍️ Xabar matnini yozing:", reply_markup=cancel_kb())


@router.message(BroadcastSt.text)
async def bc_preview(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("❌", reply_markup=admin_menu_kb()); return
    await state.update_data(text=message.text); await state.set_state(BroadcastSt.confirm)
    b = InlineKeyboardBuilder()
    b.button(text="✅ Yuborish", callback_data="bc_yes")
    b.button(text="❌ Bekor", callback_data="bc_no")
    await message.answer("📋 Ko'rinish:\n\n" + message.text, parse_mode="HTML")
    await message.answer("Yuborilsinmi?", reply_markup=b.as_markup())


@router.callback_query(F.data == "bc_no")
async def bc_no(callback: types.CallbackQuery, state: FSMContext):
    await state.clear(); await callback.message.edit_text("❌ Bekor.")


@router.callback_query(F.data == "bc_yes", BroadcastSt.confirm)
async def bc_send(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data(); text = data["text"]; await state.clear()
    ids = await get_active_user_ids(session)
    await callback.message.edit_text(f"📤 Yuborilmoqda... 0/{len(ids)}")
    sent = failed = 0
    for i, uid in enumerate(ids, 1):
        try:
            await callback.bot.send_message(uid, text, parse_mode="HTML"); sent += 1
        except Exception: failed += 1
        if i % 25 == 0: await asyncio.sleep(1)
    await save_broadcast(session, callback.from_user.id, text, sent, failed)
    await callback.message.edit_text(f"✅ <b>Yuborildi!</b>\n\n✅ {sent}  |  ❌ {failed}", parse_mode="HTML")
