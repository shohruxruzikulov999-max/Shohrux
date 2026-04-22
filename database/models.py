"""
database/models.py
"""
from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Text, Float
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings

engine = create_async_engine(
    settings.database_url, echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id   = Column(BigInteger, unique=True, nullable=False, index=True)
    username      = Column(String(64), nullable=True)
    first_name    = Column(String(128), nullable=True)
    last_name     = Column(String(128), nullable=True)
    language_code = Column(String(10), nullable=True)
    is_bot        = Column(Boolean, default=False)
    is_premium    = Column(Boolean, default=False)
    is_banned     = Column(Boolean, default=False)
    created_at    = Column(DateTime, default=datetime.utcnow)
    last_active   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def full_name(self):
        return " ".join(filter(None, [self.first_name, self.last_name])) or "Nomsiz"

class Product(Base):
    __tablename__ = "products"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    price       = Column(Float, nullable=False, default=0)
    emoji       = Column(String(8), default="📦")
    category    = Column(String(64), nullable=True, default="Asosiy")
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(BigInteger, nullable=False, index=True)
    product_id = Column(Integer, nullable=True)
    product    = Column(String(128), nullable=False)
    quantity   = Column(Integer, default=1)
    price      = Column(Float, default=0)
    status     = Column(String(32), default="pending")
    note       = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class BroadcastLog(Base):
    __tablename__ = "broadcast_logs"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    admin_id     = Column(BigInteger, nullable=False)
    message_text = Column(Text, nullable=False)
    total_sent   = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    created_at   = Column(DateTime, default=datetime.utcnow)

async def init_db():
    import os; os.makedirs("data", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as s:
        from sqlalchemy import select
        if not (await s.execute(select(Product).limit(1))).scalar_one_or_none():
            s.add_all([
                Product(name="Burger",   emoji="🍔", price=35000, category="Ovqat",    description="Mazali burger"),
                Product(name="Pizza",    emoji="🍕", price=65000, category="Ovqat",    description="Italyan pizza"),
                Product(name="Sushi",    emoji="🍣", price=80000, category="Ovqat",    description="Yapon oshxonasi"),
                Product(name="Kofe",     emoji="☕", price=15000, category="Ichimlik",  description="Issiq kofe"),
                Product(name="Choy",     emoji="🍵", price=10000, category="Ichimlik",  description="Yashil choy"),
            ])
            await s.commit()

async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
