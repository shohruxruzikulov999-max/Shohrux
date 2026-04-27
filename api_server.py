"""
api_server.py — WebApp uchun mahsulotlar API si
"""
from aiohttp import web
from database.models import AsyncSessionLocal, Product
from sqlalchemy import select
import json

async def get_products(request):
    """GET /api/products — faol mahsulotlar"""
    async with AsyncSessionLocal() as session:
        r = await session.execute(
            select(Product).where(Product.is_active == True).order_by(Product.id)
        )
        products = r.scalars().all()
        data = [
            {
                "id": p.id,
                "name": p.name,
                "price": p.price,
                "category": p.category or "",
                "photo_url": p.photo_url or "",
                "description": p.description or "",
            }
            for p in products
        ]
    return web.Response(
        text=json.dumps(data, ensure_ascii=False),
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )

async def handle_options(request):
    return web.Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
        }
    )

def create_app():
    app = web.Application()
    app.router.add_get("/api/products", get_products)
    app.router.add_options("/api/products", handle_options)
    return app