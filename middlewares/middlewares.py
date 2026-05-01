from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import settings
from database.models import AsyncSessionLocal
from database.crud import get_or_create_user

class DatabaseMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        async with AsyncSessionLocal() as session:
            data["session"] = session
            tg_user = None
            if isinstance(event, Message) and event.from_user:
                tg_user = event.from_user
            elif isinstance(event, CallbackQuery) and event.from_user:
                tg_user = event.from_user
            if tg_user and not tg_user.is_bot:
                user, created = await get_or_create_user(session, tg_user)
                data["db_user"] = user
                data["is_new_user"] = created
            return await handler(event, data)

class BanCheckMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        db_user = data.get("db_user")
        if db_user and db_user.is_banned:
            if isinstance(event, Message):
                await event.answer("🚫 Siz botdan bloklangansiz.")
            return
        return await handler(event, data)

class AdminMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        uid = None
        if isinstance(event, Message) and event.from_user:
            uid = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            uid = event.from_user.id
        data["is_admin"] = uid in settings.admin_list
        return await handler(event, data)
