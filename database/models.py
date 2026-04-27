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
    is_banned     = Column(Boolean, default=False)
    created_at    = Column(DateTime, default=datetime.utcnow)
    last_active   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def full_name(self):
        return " ".join(filter(None,[self.first_name,self.last_name])) or "Nomsiz"

class Product(Base):
    __tablename__ = "products"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    price       = Column(Float, nullable=False, default=0)
    photo_url   = Column(String(512), nullable=True)
    category    = Column(String(64), nullable=True, default="Asosiy")
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    user_id      = Column(BigInteger, nullable=False, index=True)
    telegram_username = Column(String(64), nullable=True)
    customer_name    = Column(String(128), nullable=True)
    customer_phone   = Column(String(32), nullable=True)
    customer_address = Column(Text, nullable=True)
    customer_note    = Column(Text, nullable=True)
    items_json   = Column(Text, nullable=True)   # JSON ro'yxat
    total_price  = Column(Float, default=0)
    status       = Column(String(32), default="pending")
    created_at   = Column(DateTime, default=datetime.utcnow)

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

async def get_session():
    async with AsyncSessionLocal() as session:
        yield session