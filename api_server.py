from aiohttp import web
from database.models import AsyncSessionLocal, Product
from sqlalchemy import select
import json, os


async def get_products(request):
    async with AsyncSessionLocal() as session:
        r = await session.execute(
            select(Product).where(Product.is_active == True).order_by(Product.id)
        )
        products = r.scalars().all()
        data = [
            {"id": p.id, "name": p.name, "price": p.price,
             "category": p.category or "", "photo_url": p.photo_url or "",
             "description": p.description or ""}
            for p in products
        ]
    return web.Response(
        text=json.dumps(data, ensure_ascii=False),
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )


async def serve_webapp(request):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp", "index.html")
    if os.path.exists(path):
        return web.FileResponse(path)
    return web.Response(text="Not found", status=404)


def create_app():
    app = web.Application()
    app.router.add_get("/api/products", get_products)
    app.router.add_options("/api/products", lambda r: web.Response(headers={"Access-Control-Allow-Origin": "*"}))
    app.router.add_get("/webapp", serve_webapp)
    app.router.add_get("/webapp/", serve_webapp)
    app.router.add_get("/", serve_webapp)
    return app
