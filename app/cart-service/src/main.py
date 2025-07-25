import os
import httpx
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from pydantic import BaseModel, UUID4
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from jose import JWTError, jwt
import logging

# 1. Импорт необходимых классов из prometheus_client
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram

# Настройки
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
ORDER_SERVICE_URL = os.environ.get("ORDER_SERVICE_URL", "http://order-service:8002")
SECRET_KEY = os.environ.get("SECRET_KEY", "supersecretkey123")
ALGORITHM = "HS256"

# In-memory хранилища
carts_db: Dict[str, Dict[str, Any]] = {}
recent_views_db: Dict[str, List[Dict]] = {}

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Создание приложения FastAPI
app = FastAPI()

# 2. Инструментация приложения и определение кастомных метрик
instrumentator = Instrumentator(excluded_handlers=["/health"]).instrument(app).expose(app)

# Метрика для отслеживания стоимости и размера корзины при checkout
CART_VALUE_CENTS = Histogram(
    'cart_value_cents',
    'The value of a cart in cents at checkout',
    buckets=[1000, 2500, 5000, 7500, 10000, 15000, 20000, 50000]  # Бакеты от $10 до $500
)
CART_ITEMS_COUNT = Histogram(
    'cart_items_count',
    'Total number of items (sum of quantities) in a cart at checkout',
    buckets=[1, 2, 3, 5, 8, 13, 21]  # Последовательность Фибоначчи для малых чисел
)

# Метрика для отслеживания популярных товаров
ITEMS_ADDED_TO_CART_TOTAL = Counter(
    'items_added_to_cart_total',
    'Total number of times a product has been added to a cart',
    ['product_name']
)

# Метрика для отслеживания общего числа оформленных заказов
CHECKOUTS_TOTAL = Counter(
    'checkouts_total',
    'Total number of successful checkouts initiated from cart-service'
)


# Модели данных
class CartItemCreate(BaseModel):
    product_id: UUID4
    quantity: int

class CartItemUpdate(BaseModel):
    quantity: int

class CartItem(BaseModel):
    id: UUID4
    product_id: UUID4
    name: str
    price: float
    quantity: int
    total_price: float

class Cart(BaseModel):
    items: List[CartItem]
    total: float

class Category(BaseModel):
    name: str
    product_count: int

class RecentView(BaseModel):
    product_id: UUID4
    viewed_at: str

# Вспомогательные функции
async def get_user_id(authorization: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)) -> str:
    if x_user_id:
        return x_user_id
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = parts[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username:
            return username
    except JWTError:
        pass
    return token

async def get_product_info(product_id: UUID4) -> dict:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_URL}/products/{product_id}")
            response.raise_for_status()
            product_data = response.json()
            logger.info(f"Product data received: {product_data}")
            return product_data
    except httpx.RequestError as e:
        logger.error(f"Could not connect to backend service: {e}")
        raise HTTPException(status_code=503, detail="Product service unavailable")
    except httpx.HTTPStatusError as e:
        logger.error(f"Error from backend service: {e.response.status_code} - {e.response.text}")
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Product with id {product_id} not found")
        raise HTTPException(status_code=503, detail="Product service error")

def get_user_cart(user_id: str) -> dict:
    if user_id not in carts_db:
        carts_db[user_id] = {"items": {}}
    return carts_db[user_id]

def calculate_cart_total(cart: dict) -> float:
    return sum(item["total_price"] for item in cart["items"].values())

def add_recent_view(user_id: str, product_id: str):
    views = recent_views_db.setdefault(user_id, [])
    views.insert(0, {"product_id": product_id, "viewed_at": datetime.now().isoformat()})
    recent_views_db[user_id] = [dict(t) for t in {tuple(d.items()) for d in views}][:10]

# Маршруты API
@app.get("/")
async def root():
    return {"message": "Cart Service API"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "cart-service"}

@app.get("/cart/", response_model=Cart)
async def get_cart(user_id: str = Depends(get_user_id)):
    cart = get_user_cart(user_id)
    items = list(cart["items"].values())
    total = calculate_cart_total(cart)
    return {"items": items, "total": total}

@app.post("/cart/items", response_model=CartItem)
async def add_to_cart(item: CartItemCreate, user_id: str = Depends(get_user_id)):
    product = await get_product_info(item.product_id)
    logger.info(f"Checking stock: product stock_count={product.get('stock_count')}, requested quantity={item.quantity}")
    if product.get("stock_count", 0) < item.quantity:
        raise HTTPException(status_code=400, detail="Not enough items in stock")
    
    cart = get_user_cart(user_id)
    item_id = str(uuid.uuid4())
    price = float(product["price"])
    
    # 3. Инкремент метрики популярности товара
    ITEMS_ADDED_TO_CART_TOTAL.labels(product_name=product["name"]).inc()
    
    cart["items"][item_id] = {
        "id": item_id,
        "product_id": str(item.product_id),
        "name": product["name"],
        "price": price,
        "quantity": item.quantity,
        "total_price": price * item.quantity
    }
    return cart["items"][item_id]

@app.put("/cart/items/{item_id}", response_model=CartItem)
async def update_cart_item(item_id: UUID4, item_update: CartItemUpdate, user_id: str = Depends(get_user_id)):
    cart = get_user_cart(user_id)
    if str(item_id) not in cart["items"]:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    
    cart_item = cart["items"][str(item_id)]
    product = await get_product_info(UUID4(cart_item["product_id"]))
    if product.get("stock_count", 0) < item_update.quantity:
        raise HTTPException(status_code=400, detail="Not enough items in stock")
        
    cart_item["quantity"] = item_update.quantity
    cart_item["total_price"] = float(product["price"]) * item_update.quantity
    return cart_item

@app.delete("/cart/items/{item_id}")
async def remove_from_cart(item_id: UUID4, user_id: str = Depends(get_user_id)):
    cart = get_user_cart(user_id)
    if str(item_id) not in cart["items"]:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    del cart["items"][str(item_id)]
    return {"message": "Item removed from cart"}

@app.post("/cart/checkout")
async def checkout(authorization: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)):
    user_id = await get_user_id(authorization, x_user_id)
    cart = get_user_cart(user_id)
    
    if not cart["items"]:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # 4. Сбор метрик по корзине ПЕРЕД отправкой заказа и очисткой
    cart_total_value = calculate_cart_total(cart)
    cart_total_items = sum(item["quantity"] for item in cart["items"].values())

    CART_VALUE_CENTS.observe(cart_total_value * 100) # Переводим в центы для точности
    CART_ITEMS_COUNT.observe(cart_total_items)
    CHECKOUTS_TOTAL.inc()
    
    try:
        async with httpx.AsyncClient() as client:
            order_items = [{"product_id": v["product_id"], "name": v["name"], "price": v["price"], "quantity": v["quantity"]} for v in cart["items"].values()]
            headers = {"X-User-ID": user_id}
            if authorization:
                headers["Authorization"] = authorization
            
            order_data = {"items": order_items, "total": cart_total_value}
            
            response = await client.post(f"{ORDER_SERVICE_URL}/orders/", json=order_data, headers=headers)
            response.raise_for_status()
            
            # Очищаем корзину только после успешного оформления заказа
            cart["items"] = {}
            return response.json()
            
    except httpx.RequestError as e:
        logger.error(f"Could not connect to order service: {e}")
        raise HTTPException(status_code=503, detail="Order service unavailable")
    except httpx.HTTPStatusError as e:
        logger.error(f"Error from order service: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Order service error: {e.response.text}")

@app.delete("/cart/")
async def clear_cart(user_id: str = Depends(get_user_id)):
    cart = get_user_cart(user_id)
    cart["items"] = {}
    return {"message": "Cart cleared"}

@app.post("/products/{product_id}/view")
async def record_product_view(product_id: UUID4, user_id: str = Depends(get_user_id)):
    await get_product_info(product_id)
    add_recent_view(user_id, str(product_id))
    return {"message": "Product view recorded"}

@app.get("/products/recent-views", response_model=List[RecentView])
async def get_recent_views(user_id: str = Depends(get_user_id)):
    return recent_views_db.get(user_id, [])

# Административные маршруты
@app.get("/carts/")
async def get_all_carts(admin: Optional[bool] = Header(False)):
    if not admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return carts_db