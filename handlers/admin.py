"""
handlers/admin.py — Admin: statistika, foydalanuvchilar, buyurtmalar,
                    mahsulot CRUD (qo'shish/tahrirlash/o'chirish), broadcast
"""
import asyncio, logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from utils.filters import IsAdmin
from utils.keyboards import (admin_menu_kb, main_menu_kb, cancel_kb,
                              product_manage_kb)
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


# ── FSM States ────────────────────────────────────────────────────────────────

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


# ── /admin ────────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("⚙️ <b>Admin panel</b>", reply_markup=admin_menu_kb(), parse_mode="HTML")


@router.message(F.text == "🔙 Orqaga")
async def back_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Asosiy menyu", reply_markup=main_menu_kb())


# ── Statistika ────────────────────────────────────────────────────────────────

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
    text = f"👥 <b>So'nggi 30 foydalanuvchi ({total} jami):</b>\n\n"
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
    except ValueError: await message.answer("❗ ID raqam bo'lishi kerak")


@router.message(Command("unban"))
async def unban_cmd(message: types.Message, session: AsyncSession):
    args = message.text.split()
    if len(args) < 2: await message.answer("❗ /unban <id>"); return
    try:
        ok = await unban_user(session, int(args[1]))
        await message.answer(f"{'✅ Blok ochildi' if ok else '❌ Topilmadi'}: <code>{args[1]}</code>", parse_mode="HTML")
    except ValueError: await message.answer("❗ ID raqam bo'lishi kerak")


# ── Buyurtmalar ───────────────────────────────────────────────────────────────

@router.message(F.text == "📦 Buyurtmalar")
async def orders_list(message: types.Message, session: AsyncSession):
    orders = await get_orders(session, limit=20)
    if not orders: await message.answer("📭 Buyurtmalar yo'q."); return
    icons = {"pending":"⏳","confirmed":"✅","cancelled":"❌"}
    text = f"📦 <b>Oxirgi {len(orders)} buyurtma:</b>\n\n"
    for o in orders:
        text += f"{icons.get(o.status,'📦')} #{o.id} | <code>{o.user_id}</code> | {o.product} ×{o.quantity} = {int(o.price):,} so'm\n"
    await message.answer(text[:4096], parse_mode="HTML")


# ════════════════════════════════════════════════════════════════════════════════
#  MAHSULOT BOSHQARUVI
# ════════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "🛍 Mahsulotlar")
async def products_admin(message: types.Message, session: AsyncSession):
    prods = await get_all_products(session)
    b = InlineKeyboardBuilder()
    for p in prods:
        status = "🟢" if p.is_active else "🔴"
        b.button(text=f"{status} {p.emoji} {p.name} — {int(p.price):,}",
                 callback_data=f"padmin:{p.id}")
    b.button(text="➕ Yangi mahsulot", callback_data="prod_new")
    b.adjust(1)
    await message.answer(
        f"🛍 <b>Mahsulotlar ({len(prods)} ta):</b>\n\n"
        "Mahsulotni bosing — boshqaring.\n"
        "🟢 Faol  |  🔴 Nofaol",
        reply_markup=b.as_markup(), parse_mode="HTML",
    )


# ─── Mahsulot detail ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("padmin:"))
async def product_detail(callback: types.CallbackQuery, session: AsyncSession):
    pid = int(callback.data.split(":")[1])
    p = await get_product(session, pid)
    if not p: await callback.answer("Topilmadi"); return
    status = "🟢 Faol" if p.is_active else "🔴 Nofaol"
    await callback.message.edit_text(
        f"{p.emoji} <b>{p.name}</b>\n\n"
        f"📝 Tavsif: {p.description or '—'}\n"
        f"💰 Narx: {int(p.price):,} so'm\n"
        f"🗂 Kategoriya: {p.category or '—'}\n"
        f"📌 Status: {status}\n"
        f"🆔 ID: {p.id}",
        reply_markup=product_manage_kb(p.id, p.is_active),
        parse_mode="HTML",
    )
    await callback.answer()


# ─── Yangi mahsulot qo'shish (FSM) ──────────────────────────────────────────

@router.callback_query(F.data == "prod_new")
async def prod_new_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ProductAdd.name)
    await callback.message.answer("✏️ <b>Yangi mahsulot</b>\n\n1/5 — Nomini kiriting:", parse_mode="HTML", reply_markup=cancel_kb())
    await callback.answer()

@router.message(ProductAdd.name)
async def prod_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("❌ Bekor qilindi", reply_markup=admin_menu_kb()); return
    await state.update_data(name=message.text)
    await state.set_state(ProductAdd.price)
    await message.answer("2/5 — Narxini kiriting (so'mda, faqat raqam):")

@router.message(ProductAdd.price)
async def prod_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("❌", reply_markup=admin_menu_kb()); return
    try:
        price = float(message.text.replace(" ","").replace(",","."))
    except ValueError:
        await message.answer("❗ Faqat raqam kiriting:"); return
    await state.update_data(price=price)
    await state.set_state(ProductAdd.photo)
    await message.answer("3/5 — Mahsulot rasmini yuboring 📸\n(rasm yo'q bo'lsa yo'q deb yozing):")

@router.message(ProductAdd.photo)
async def prod_photo(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("❌", reply_markup=admin_menu_kb()); return

    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
        await state.update_data(photo_id=photo_id)
    elif message.text and message.text.lower() in ("yoq", "yo'q", "-", "skip"):
        await state.update_data(photo_id=None)
    else:
        await message.answer("📸 Iltimos rasm yuboring (yoki yo'q deb yozing):")
        return

    await state.set_state(ProductAdd.category)
    b = InlineKeyboardBuilder()
    for cat in ["Ovqat","Ichimlik","Shirinlik","Boshqa"]:
        b.button(text=cat, callback_data=f"cat:{cat}")
    b.adjust(2)
    await message.answer("4/5 — Kategoriyani tanlang:", reply_markup=b.as_markup())

@router.callback_query(F.data.startswith("cat:"), ProductAdd.category)
async def prod_category(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(category=callback.data.split(":")[1])
    await state.set_state(ProductAdd.desc)
    await callback.message.answer("5/5 — Tavsifni kiriting (yoki 'yo'q' deb yozing):")
    await callback.answer()

@router.message(ProductAdd.desc)
async def prod_desc_finish(message: types.Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("❌", reply_markup=admin_menu_kb()); return
    data = await state.get_data()
    desc = "" if message.text.lower() in ("yo'q","yoq","-","") else message.text
    p = await create_product(session,
        name=data["name"], price=data["price"],
        photo_id=data.get("photo_id"), category=data["category"], description=desc)
    await state.clear()
    await message.answer(
        f"✅ <b>Mahsulot qo'shildi!</b>\n\n"
        f"{p.emoji} <b>{p.name}</b>\n"
        f"💰 {int(p.price):,} so'm\n"
        f"🗂 {p.category}",
        reply_markup=admin_menu_kb(), parse_mode="HTML",
    )


# ─── Tahrirlash (FSM) ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("prod_edit:"))
async def prod_edit_start(callback: types.CallbackQuery, state: FSMContext):
    pid = int(callback.data.split(":")[1])
    await state.update_data(edit_pid=pid)
    await state.set_state(ProductEdit.field)
    b = InlineKeyboardBuilder()
    fields = [("📛 Nom","name"),("💰 Narx","price"),
              ("😀 Emoji","emoji"),("🗂 Kategoriya","category"),("📝 Tavsif","description")]
    for label, key in fields:
        b.button(text=label, callback_data=f"editf:{key}")
    b.button(text="❌ Bekor", callback_data="edit_cancel")
    b.adjust(2, 2, 1, 1)
    await callback.message.edit_text("✏️ Qaysi maydonni tahrirlaysiz?", reply_markup=b.as_markup())
    await callback.answer()

@router.callback_query(F.data == "edit_cancel")
async def edit_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear(); await callback.message.delete(); await callback.answer("Bekor qilindi")

@router.callback_query(F.data.startswith("editf:"), ProductEdit.field)
async def prod_edit_field(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    await state.update_data(edit_field=field)
    await state.set_state(ProductEdit.value)
    labels = {"name":"yangi nom","price":"yangi narx (raqam)","emoji":"yangi emoji",
              "category":"yangi kategoriya","description":"yangi tavsif"}
    await callback.message.answer(f"✏️ {labels.get(field,'yangi qiymat')} ni kiriting:")
    await callback.answer()

@router.message(ProductEdit.value)
async def prod_edit_value(message: types.Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    pid, field = data["edit_pid"], data["edit_field"]
    value = message.text
    if field == "price":
        try: value = float(value.replace(" ","").replace(",","."))
        except ValueError: await message.answer("❗ Faqat raqam:"); return
    await update_product(session, pid, **{field: value})
    await state.clear()
    p = await get_product(session, pid)
    await message.answer(
        f"✅ <b>Yangilandi!</b>\n\n{p.emoji} <b>{p.name}</b> — {int(p.price):,} so'm",
        reply_markup=admin_menu_kb(), parse_mode="HTML",
    )


# ─── O'chirish ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("prod_del:"))
async def prod_del_confirm(callback: types.CallbackQuery):
    pid = callback.data.split(":")[1]
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, o'chirish", callback_data=f"prod_del_ok:{pid}")
    b.button(text="❌ Bekor",          callback_data=f"padmin:{pid}")
    b.adjust(2)
    await callback.message.edit_text("⚠️ Mahsulotni o'chirishni tasdiqlaysizmi?", reply_markup=b.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("prod_del_ok:"))
async def prod_del_exec(callback: types.CallbackQuery, session: AsyncSession):
    pid = int(callback.data.split(":")[1])
    ok = await delete_product(session, pid)
    await callback.message.edit_text("✅ Mahsulot o'chirildi." if ok else "❌ Topilmadi.")
    await callback.answer()


# ─── Toggle active ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("prod_toggle:"))
async def prod_toggle(callback: types.CallbackQuery, session: AsyncSession):
    pid = int(callback.data.split(":")[1])
    new_state = await toggle_product(session, pid)
    if new_state is None: await callback.answer("Topilmadi"); return
    label = "🟢 Yoqildi" if new_state else "🔴 O'chirildi"
    await callback.answer(label, show_alert=True)
    # Refresh detail
    p = await get_product(session, pid)
    status = "🟢 Faol" if p.is_active else "🔴 Nofaol"
    await callback.message.edit_text(
        f"{p.emoji} <b>{p.name}</b>\n\n"
        f"📝 {p.description or '—'}\n💰 {int(p.price):,} so'm\n"
        f"🗂 {p.category or '—'}\n📌 {status}",
        reply_markup=product_manage_kb(p.id, p.is_active),
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════════════════════════════════
#  BROADCAST
# ════════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "📢 Broadcast")
async def bc_start(message: types.Message, state: FSMContext):
    await state.set_state(BroadcastSt.text)
    await message.answer("✍️ Xabar matnini yozing (HTML qo'llab-quvvatlanadi):", reply_markup=cancel_kb())

@router.message(BroadcastSt.text)
async def bc_preview(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear(); await message.answer("❌", reply_markup=admin_menu_kb()); return
    await state.update_data(text=message.text); await state.set_state(BroadcastSt.confirm)
    b = InlineKeyboardBuilder()
    b.button(text="✅ Yuborish", callback_data="bc_yes")
    b.button(text="❌ Bekor",   callback_data="bc_no")
    await message.answer("📋 <b>Ko'rinish:</b>\n\n" + message.text, parse_mode="HTML")
    await message.answer("Yuborilsinmi?", reply_markup=b.as_markup())

@router.callback_query(F.data == "bc_no")
async def bc_no(callback: types.CallbackQuery, state: FSMContext):
    await state.clear(); await callback.message.edit_text("❌ Bekor qilindi.")

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
    await callback.message.edit_text(
        f"✅ <b>Yuborildi!</b>\n\n✅ {sent} ta  |  ❌ {failed} ta xato",
        parse_mode="HTML",
    )