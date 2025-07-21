import os
import httpx
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from pydantic import BaseModel, UUID4
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

# Настройки
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
ORDER_SERVICE_URL = os.environ.get("ORDER_SERVICE_URL", "http://order-service:8002")

# In-memory хранилище корзин
carts_db: Dict[str, Dict[str, Any]] = {}

# In-memory хранилище недавно просмотренных товаров
recent_views_db: Dict[str, List[Dict]] = {}

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

class PaginationMetadata(BaseModel):
    total: int
    page: int
    pages: int
    has_next: bool
    has_prev: bool

class ProductOut(BaseModel):
    product_id: UUID4
    name: str
    category: str
    price: float

class PaginatedProducts(PaginationMetadata):
    items: List[ProductOut]

class RecentView(BaseModel):
    product_id: UUID4
    viewed_at: str

# Вспомогательные функции
async def get_user_id(authorization: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)) -> str:
    """Получение идентификатора пользователя из заголовка Authorization или X-User-ID"""
    if x_user_id:
        return x_user_id
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    # Извлекаем user_id из токена
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    # Возвращаем subject из токена как user_id
    # В реальном приложении здесь должна быть декодирование JWT
    return parts[1]  # Используем токен как идентификатор пользователя

async def get_product_info(product_id: UUID4) -> dict:
    """Получение информации о товаре из бэкенд-сервиса"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_URL}/products/{product_id}")
            if response.status_code != 200:
                raise HTTPException(status_code=503, detail="Product service unavailable")
            return response.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Product service unavailable")

async def get_categories() -> List[Category]:
    """Получение списка категорий из бэкенд-сервиса"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_URL}/products/categories/list")
            if response.status_code != 200:
                raise HTTPException(status_code=503, detail="Product service unavailable")
            return [Category(**category) for category in response.json()]
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Product service unavailable")

async def get_products_by_category(
    category: str, 
    skip: int = 0, 
    limit: int = 100,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
    min_price: Optional[float] = None,
    max_price: Optional[float] = None
) -> PaginatedProducts:
    """Получение товаров по категории из бэкенд-сервиса с пагинацией, сортировкой и фильтрацией"""
    try:
        query_params = {
            "skip": skip,
            "limit": limit
        }
        if sort_by:
            query_params["sort_by"] = sort_by
            query_params["sort_order"] = sort_order
        if min_price is not None:
            query_params["min_price"] = min_price
        if max_price is not None:
            query_params["max_price"] = max_price
            
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BACKEND_URL}/products/by-category/{category}",
                params=query_params
            )
            if response.status_code != 200:
                raise HTTPException(status_code=503, detail="Product service unavailable")
            return response.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Product service unavailable")

def get_user_cart(user_id: str) -> dict:
    """Получение корзины пользователя или создание новой"""
    if user_id not in carts_db:
        carts_db[user_id] = {"items": {}}
    return carts_db[user_id]

def calculate_cart_total(cart: dict) -> float:
    """Расчет общей стоимости корзины"""
    return sum(item["total_price"] for item in cart["items"].values())

def get_user_recent_views(user_id: str) -> list:
    """Получение недавно просмотренных товаров пользователя"""
    if user_id not in recent_views_db:
        recent_views_db[user_id] = []
    return recent_views_db[user_id]

def add_recent_view(user_id: str, product_id: str):
    """Добавление товара в список недавно просмотренных"""
    views = get_user_recent_views(user_id)
    
    # Проверяем, есть ли уже этот товар в списке
    for view in views:
        if view["product_id"] == product_id:
            # Если есть, обновляем время просмотра и перемещаем в начало списка
            views.remove(view)
            break
    
    # Добавляем товар в начало списка
    views.insert(0, {
        "product_id": product_id,
        "viewed_at": datetime.now().isoformat()
    })
    
    # Ограничиваем список 10 последними просмотренными товарами
    recent_views_db[user_id] = views[:10]

# Создание приложения FastAPI
app = FastAPI()

# Маршруты API
@app.get("/")
async def root():
    return {"message": "Cart Service API"}

@app.get("/categories/", response_model=List[Category])
async def get_all_categories():
    """Получение списка всех категорий товаров"""
    return await get_categories()

@app.get("/products/category/{category}")
async def get_category_products(
    category: str, 
    skip: int = 0, 
    limit: int = 100,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
    min_price: Optional[float] = None,
    max_price: Optional[float] = None
):
    """Получение списка товаров по категории с пагинацией, сортировкой и фильтрацией"""
    return await get_products_by_category(
        category, 
        skip, 
        limit, 
        sort_by, 
        sort_order, 
        min_price, 
        max_price
    )

@app.get("/cart/", response_model=Cart)
async def get_cart(user_id: str = Depends(get_user_id)):
    """Получение текущей корзины пользователя"""
    cart = get_user_cart(user_id)
    items = list(cart["items"].values())
    total = calculate_cart_total(cart)
    return {"items": items, "total": total}

@app.post("/cart/items", response_model=CartItem)
async def add_to_cart(item: CartItemCreate, user_id: str = Depends(get_user_id)):
    """Добавление товара в корзину"""
    # Получаем информацию о товаре
    product = await get_product_info(item.product_id)
    
    # Проверяем наличие товара
    if product["stock_count"] < item.quantity:
        raise HTTPException(status_code=400, detail="Not enough items in stock")
    
    # Добавляем товар в корзину
    cart = get_user_cart(user_id)
    item_id = str(uuid.uuid4())
    price = float(product["price"])
    total_price = price * item.quantity
    
    cart["items"][item_id] = {
        "id": item_id,
        "product_id": str(item.product_id),
        "name": product["name"],
        "price": price,
        "quantity": item.quantity,
        "total_price": total_price
    }
    
    return cart["items"][item_id]

@app.put("/cart/items/{item_id}", response_model=CartItem)
async def update_cart_item(item_id: UUID4, item_update: CartItemUpdate, user_id: str = Depends(get_user_id)):
    """Изменение количества товара в корзине"""
    cart = get_user_cart(user_id)
    
    # Проверяем наличие товара в корзине
    if str(item_id) not in cart["items"]:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    
    # Получаем текущий товар из корзины
    cart_item = cart["items"][str(item_id)]
    
    # Получаем информацию о товаре для проверки наличия
    product = await get_product_info(UUID4(cart_item["product_id"]))
    
    # Проверяем наличие товара
    if product["stock_count"] < item_update.quantity:
        raise HTTPException(status_code=400, detail="Not enough items in stock")
    
    # Обновляем количество и стоимость
    cart_item["quantity"] = item_update.quantity
    cart_item["total_price"] = float(product["price"]) * item_update.quantity
    
    return cart_item

@app.delete("/cart/items/{item_id}")
async def remove_from_cart(item_id: UUID4, user_id: str = Depends(get_user_id)):
    """Удаление товара из корзины"""
    cart = get_user_cart(user_id)
    
    # Проверяем наличие товара в корзине
    if str(item_id) not in cart["items"]:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    
    # Удаляем товар из корзины
    del cart["items"][str(item_id)]
    
    return {"message": "Item removed from cart"}

@app.get("/cart/total")
async def get_cart_total(user_id: str = Depends(get_user_id)):
    """Получение общей стоимости корзины"""
    cart = get_user_cart(user_id)
    total = calculate_cart_total(cart)
    return {"total": total}

@app.post("/cart/checkout")
async def checkout(background_tasks: BackgroundTasks, authorization: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)):
    """Оформление заказа из корзины"""
    # Получаем user_id
    user_id = await get_user_id(authorization, x_user_id)
    
    cart = get_user_cart(user_id)
    
    # Проверяем, что корзина не пуста
    if not cart["items"]:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Создаем заказ
    try:
        async with httpx.AsyncClient() as client:
            # Подготавливаем данные для заказа
            order_items = []
            for item in cart["items"].values():
                order_items.append({
                    "product_id": item["product_id"],
                    "name": item["name"],
                    "price": item["price"],
                    "quantity": item["quantity"]
                })
            
            # Отправляем запрос на создание заказа
            headers = {"X-User-ID": user_id}
            
            # Если есть заголовок Authorization, передаем его
            if authorization:
                headers["Authorization"] = authorization
            
            order_data = {
                "items": order_items,
                "total": calculate_cart_total(cart)
            }
            
            response = await client.post(
                f"{ORDER_SERVICE_URL}/orders/",
                json=order_data,
                headers=headers
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=503, detail="Order service unavailable")
            
            # Очищаем корзину после успешного оформления заказа
            cart["items"] = {}
            
            return response.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Order service unavailable")

@app.delete("/cart/")
async def clear_cart(user_id: str = Depends(get_user_id)):
    """Очистка корзины"""
    cart = get_user_cart(user_id)
    cart["items"] = {}
    return {"message": "Cart cleared"}

# Новые API для отслеживания просмотренных товаров
@app.post("/products/{product_id}/view")
async def record_product_view(product_id: UUID4, user_id: str = Depends(get_user_id)):
    """Запись о просмотре товара пользователем"""
    # Проверяем существование товара
    await get_product_info(product_id)
    
    # Добавляем товар в список недавно просмотренных
    add_recent_view(user_id, str(product_id))
    
    return {"message": "Product view recorded"}

@app.get("/products/recent-views", response_model=List[RecentView])
async def get_recent_views(user_id: str = Depends(get_user_id)):
    """Получение списка недавно просмотренных товаров пользователя"""
    views = get_user_recent_views(user_id)
    return views

# Рекомендации товаров на основе просмотренных
@app.get("/products/recommendations")
async def get_recommendations(user_id: str = Depends(get_user_id)):
    """Получение рекомендаций товаров на основе просмотренных"""
    views = get_user_recent_views(user_id)
    
    if not views:
        # Если нет просмотренных товаров, возвращаем популярные товары
        return await get_category_products("Популярные", limit=10)
    
    # Собираем категории просмотренных товаров
    viewed_categories = []
    for view in views:
        try:
            product = await get_product_info(view["product_id"])
            if product["category"] not in viewed_categories:
                viewed_categories.append(product["category"])
        except HTTPException:
            # Игнорируем несуществующие товары
            continue
    
    # Если не нашли категорий, возвращаем популярные товары
    if not viewed_categories:
        return await get_category_products("Популярные", limit=10)
    
    # Получаем рекомендации из первой категории
    recommendations = await get_products_by_category(viewed_categories[0], limit=10)
    
    return recommendations

# Административные маршруты
@app.get("/carts/")
async def get_all_carts(admin: Optional[bool] = Header(False)):
    """Получение всех корзин (только для администраторов)"""
    if not admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return carts_db 