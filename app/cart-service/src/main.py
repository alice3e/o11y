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

# Импортируем модуль трейсинга
from src.tracing import setup_tracing, get_tracer

# Импортируем модуль профилирования
from src.profiling import profile_endpoint, profile_context, get_profile_stats, list_available_profiles

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

# Инициализация трейсинга
tracer = setup_tracing(app)
logger.info("Tracing initialized for Cart Service")

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
    with tracer.start_as_current_span("get_user_id") as span:
        if x_user_id:
            span.set_attribute("user.source", "x_user_id_header")
            return x_user_id
        if not authorization:
            span.set_attribute("error", "authorization_header_missing")
            raise HTTPException(status_code=401, detail="Authorization header missing")
        
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            span.set_attribute("error", "invalid_authorization_header")
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        token = parts[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username:
                span.set_attribute("user.source", "jwt_token")
                span.set_attribute("user.username", username)
                return username
        except JWTError as e:
            span.set_attribute("error", "jwt_decode_error")
            span.set_attribute("error.message", str(e))
        
        span.set_attribute("user.source", "raw_token")
        return token

async def get_product_info(product_id: UUID4) -> dict:
    with tracer.start_as_current_span("get_product_info") as span:
        span.set_attribute("product.id", str(product_id))
        
        try:
            async with httpx.AsyncClient() as client:
                with tracer.start_as_current_span("product_service_request") as req_span:
                    req_span.set_attribute("http.method", "GET")
                    req_span.set_attribute("http.url", f"{BACKEND_URL}/products/{product_id}")
                    
                    response = await client.get(f"{BACKEND_URL}/products/{product_id}")
                    req_span.set_attribute("http.status_code", response.status_code)
                    response.raise_for_status()
                    
                    product_data = response.json()
                    span.set_attribute("product.name", product_data.get("name"))
                    span.set_attribute("product.price", product_data.get("price"))
                    span.set_attribute("product.stock_count", product_data.get("stock_count"))
                    
                    logger.info(f"Product data received: {product_data}")
                    return product_data
                    
        except httpx.RequestError as e:
            span.set_attribute("error", "request_error")
            span.set_attribute("error.message", str(e))
            logger.error(f"Could not connect to backend service: {e}")
            raise HTTPException(status_code=503, detail="Product service unavailable")
        except httpx.HTTPStatusError as e:
            span.set_attribute("error", "http_error")
            span.set_attribute("error.status_code", e.response.status_code)
            logger.error(f"Error from backend service: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Product with id {product_id} not found")
            raise HTTPException(status_code=503, detail="Product service error")

def get_user_cart(user_id: str) -> dict:
    with tracer.start_as_current_span("get_user_cart") as span:
        span.set_attribute("user.id", user_id)
        
        if user_id not in carts_db:
            carts_db[user_id] = {"items": {}}
            span.set_attribute("cart.created", True)
        return carts_db[user_id]

def calculate_cart_total(cart: dict) -> float:
    with tracer.start_as_current_span("calculate_cart_total") as span:
        total = sum(item["total_price"] for item in cart["items"].values())
        span.set_attribute("cart.total", total)
        span.set_attribute("cart.items_count", len(cart["items"]))
        return total

def add_recent_view(user_id: str, product_id: str):
    with tracer.start_as_current_span("add_recent_view") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("product.id", product_id)
        
        views = recent_views_db.setdefault(user_id, [])
        views.insert(0, {"product_id": product_id, "viewed_at": datetime.now().isoformat()})
        recent_views_db[user_id] = [dict(t) for t in {tuple(d.items()) for d in views}][:10]
        span.set_attribute("recent_views.count", len(recent_views_db[user_id]))

# Маршруты API
@app.get("/")
async def root():
    return {"message": "Cart Service API"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "cart-service"}

@app.get("/cart/", response_model=Cart)
@profile_endpoint("get_cart")
async def get_cart(user_id: str = Depends(get_user_id)):
    with tracer.start_as_current_span("get_cart") as span:
        span.set_attribute("user.id", user_id)
        
        cart = get_user_cart(user_id)
        items = list(cart["items"].values())
        total = calculate_cart_total(cart)
        
        span.set_attribute("cart.items_count", len(items))
        span.set_attribute("cart.total", total)
        
        return {"items": items, "total": total}

@app.post("/cart/items", response_model=CartItem)
@profile_endpoint("add_to_cart")
async def add_to_cart(item: CartItemCreate, user_id: str = Depends(get_user_id)):
    with tracer.start_as_current_span("add_to_cart") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("product.id", str(item.product_id))
        span.set_attribute("item.quantity", item.quantity)
        
        with tracer.start_as_current_span("get_product_info"):
            product = await get_product_info(item.product_id)
        
        logger.info(f"Checking stock: product stock_count={product.get('stock_count')}, requested quantity={item.quantity}")
        if product.get("stock_count", 0) < item.quantity:
            span.set_attribute("error", "insufficient_stock")
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
        
        span.set_attribute("cart_item.id", item_id)
        span.set_attribute("cart_item.total_price", price * item.quantity)
        
        return cart["items"][item_id]

@app.put("/cart/items/{item_id}", response_model=CartItem)
async def update_cart_item(item_id: UUID4, item_update: CartItemUpdate, user_id: str = Depends(get_user_id)):
    with tracer.start_as_current_span("update_cart_item") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("item.id", str(item_id))
        span.set_attribute("new_quantity", item_update.quantity)
        
        cart = get_user_cart(user_id)
        
        # Сначала пробуем найти по item_id
        actual_item_id = str(item_id)
        if actual_item_id in cart["items"]:
            cart_item = cart["items"][actual_item_id]
        else:
            # Если не найден по item_id, ищем по product_id
            actual_item_id = None
            for id, item in cart["items"].items():
                if item["product_id"] == str(item_id):
                    actual_item_id = id
                    cart_item = item
                    break
            
            if not actual_item_id:
                span.set_attribute("error", "item_not_found")
                raise HTTPException(status_code=404, detail="Item not found in cart")
        
        with tracer.start_as_current_span("get_product_info"):
            product = await get_product_info(UUID4(cart_item["product_id"]))
        
        if product.get("stock_count", 0) < item_update.quantity:
            span.set_attribute("error", "insufficient_stock")
            raise HTTPException(status_code=400, detail="Not enough items in stock")
            
        cart_item["quantity"] = item_update.quantity
        cart_item["total_price"] = float(product["price"]) * item_update.quantity
        
        span.set_attribute("updated_total_price", cart_item["total_price"])
        
        return cart_item

@app.delete("/cart/items/{item_id}")
async def remove_from_cart(item_id: UUID4, user_id: str = Depends(get_user_id)):
    with tracer.start_as_current_span("remove_from_cart") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("item.id", str(item_id))
        
        cart = get_user_cart(user_id)
        
        # Сначала пробуем найти по item_id
        actual_item_id = str(item_id)
        if actual_item_id in cart["items"]:
            del cart["items"][actual_item_id]
            span.set_attribute("removed_by", "item_id")
            return {"message": "Item removed from cart"}
        else:
            # Если не найден по item_id, ищем по product_id и удаляем все такие товары
            items_to_remove = []
            for id, item in cart["items"].items():
                if item["product_id"] == str(item_id):
                    items_to_remove.append(id)
            
            if not items_to_remove:
                span.set_attribute("error", "item_not_found")
                raise HTTPException(status_code=404, detail="Item not found in cart")
            
            # Удаляем все найденные товары
            for item_id_to_remove in items_to_remove:
                del cart["items"][item_id_to_remove]
            
            span.set_attribute("removed_by", "product_id")
            span.set_attribute("items_removed_count", len(items_to_remove))
            
            return {"message": f"Removed {len(items_to_remove)} items from cart"}

@app.post("/cart/checkout")
async def checkout(authorization: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)):
    with tracer.start_as_current_span("checkout") as span:
        user_id = await get_user_id(authorization, x_user_id)
        span.set_attribute("user.id", user_id)
        
        cart = get_user_cart(user_id)
        
        if not cart["items"]:
            span.set_attribute("error", "empty_cart")
            raise HTTPException(status_code=400, detail="Cart is empty")

        # 4. Сбор метрик по корзине ПЕРЕД отправкой заказа и очисткой
        cart_total_value = calculate_cart_total(cart)
        cart_total_items = sum(item["quantity"] for item in cart["items"].values())

        span.set_attribute("cart.total_value", cart_total_value)
        span.set_attribute("cart.total_items", cart_total_items)
        
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
                
                with tracer.start_as_current_span("order_service_request") as req_span:
                    req_span.set_attribute("http.method", "POST")
                    req_span.set_attribute("http.url", f"{ORDER_SERVICE_URL}/orders/")
                    req_span.set_attribute("order.items_count", len(order_items))
                    
                    response = await client.post(f"{ORDER_SERVICE_URL}/orders/", json=order_data, headers=headers)
                    req_span.set_attribute("http.status_code", response.status_code)
                    response.raise_for_status()
                    
                    # Очищаем корзину только после успешного оформления заказа
                    cart["items"] = {}
                    span.set_attribute("cart.cleared", True)
                    
                    return response.json()
                    
        except httpx.RequestError as e:
            span.set_attribute("error", "request_error")
            span.set_attribute("error.message", str(e))
            logger.error(f"Could not connect to order service: {e}")
            raise HTTPException(status_code=503, detail="Order service unavailable")
        except httpx.HTTPStatusError as e:
            span.set_attribute("error", "http_error")
            span.set_attribute("error.status_code", e.response.status_code)
            logger.error(f"Error from order service: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Order service error: {e.response.text}")

@app.delete("/cart/")
async def clear_cart(user_id: str = Depends(get_user_id)):
    with tracer.start_as_current_span("clear_cart") as span:
        span.set_attribute("user.id", user_id)
        
        cart = get_user_cart(user_id)
        items_count = len(cart["items"])
        cart["items"] = {}
        
        span.set_attribute("items_cleared_count", items_count)
        
        return {"message": "Cart cleared"}

@app.post("/products/{product_id}/view")
async def record_product_view(product_id: UUID4, user_id: str = Depends(get_user_id)):
    with tracer.start_as_current_span("record_product_view") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("product.id", str(product_id))
        
        await get_product_info(product_id)
        add_recent_view(user_id, str(product_id))
        
        return {"message": "Product view recorded"}

@app.get("/products/recent-views", response_model=List[RecentView])
async def get_recent_views(user_id: str = Depends(get_user_id)):
    with tracer.start_as_current_span("get_recent_views") as span:
        span.set_attribute("user.id", user_id)
        
        views = recent_views_db.get(user_id, [])
        span.set_attribute("views.count", len(views))
        
        return views

# Административные маршруты
@app.get("/carts/")
async def get_all_carts(admin: Optional[bool] = Header(False)):
    with tracer.start_as_current_span("get_all_carts") as span:
        span.set_attribute("admin.access", admin)
        
        if not admin:
            span.set_attribute("error", "admin_access_denied")
            raise HTTPException(status_code=403, detail="Admin access required")
        
        span.set_attribute("carts.count", len(carts_db))
        return carts_db

# Эндпоинты для управления профилированием
@app.get("/profiling/status")
async def get_profiling_status():
    """Получение статуса профилирования"""
    return {
        "service": "cart-service",
        "enabled": os.environ.get("ENABLE_PROFILING", "false").lower() == "true",
        "profiles_directory": "/app/profiles"
    }

@app.get("/profiling/profiles")
async def list_profiles():
    """Получение списка доступных профилей для cart-service"""
    return {"profiles": list_available_profiles()}

@app.get("/profiling/profiles/{filename}/stats")
async def get_profile_stats_endpoint(filename: str):
    """Получение статистики профиля"""
    profile_path = f"/app/profiles/{filename}"
    stats = get_profile_stats(profile_path)
    return {"filename": filename, "service": "cart-service", "stats": stats}

@app.post("/profiling/manual/{operation_name}")
@profile_endpoint("manual_operation")
async def manual_profiling_test(operation_name: str):
    """Тестовый эндпоинт для ручного профилирования корзины"""
    import random
    import asyncio
    
    # Имитация различных операций с корзиной
    with profile_context(f"cart_manual_{operation_name}"):
        # Имитация работы с данными корзины
        cart_data = {}
        for i in range(500):
            cart_data[f"item_{i}"] = {
                "price": random.uniform(10, 1000),
                "quantity": random.randint(1, 5)
            }
        
        # Имитация расчета общей стоимости
        total = sum(item["price"] * item["quantity"] for item in cart_data.values())
        
        # Имитация IO операции
        await asyncio.sleep(0.05)
        
        return {
            "operation": operation_name,
            "service": "cart-service",
            "processed_items": len(cart_data),
            "total_value": total,
            "profiling_enabled": os.environ.get("ENABLE_PROFILING", "false").lower() == "true"
        }