import os
import httpx
from fastapi import FastAPI, HTTPException, Depends, Request, Query, Header
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from uuid import UUID, uuid4
from datetime import datetime

# Модели данных
class CartItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    product_id: UUID
    quantity: int
    price: float
    product_name: str

class CartItemCreate(BaseModel):
    product_id: UUID
    quantity: int

class CartItemUpdate(BaseModel):
    quantity: int

class Cart(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: str
    items: List[CartItem] = []
    total_price: float = 0.0

# Хранилище корзин (в памяти для примера)
# Структура: {user_id: Cart}
carts_db: Dict[str, Cart] = {}

# Создание приложения FastAPI
app = FastAPI(
    title="Cart Service API",
    description="Сервис для управления корзиной товаров",
    version="0.1.0",
)

# Вспомогательные функции
def get_user_id(request: Request) -> str:
    # В реальном приложении здесь была бы аутентификация
    # Для примера используем заголовок X-User-ID
    user_id = request.headers.get("X-User-ID", "anonymous")
    return user_id

def is_admin(request: Request) -> bool:
    # В реальном приложении здесь была бы проверка прав администратора
    # Для примера используем заголовок X-Admin
    return request.headers.get("X-Admin") == "true"

async def get_product_api_client():
    async with httpx.AsyncClient(base_url=f"http://{os.getenv('BACKEND_HOST', 'backend')}/api") as client:
        yield client

# Получение или создание корзины для пользователя
def get_or_create_cart(user_id: str) -> Cart:
    if user_id not in carts_db:
        carts_db[user_id] = Cart(user_id=user_id)
    return carts_db[user_id]

# Проверка авторизации (опционально)
async def verify_token(x_token: Optional[str] = Header(None)):
    if x_token is None:
        return None
    # В реальном приложении здесь была бы проверка токена через сервис пользователей
    return x_token

# Эндпоинты
@app.get("/")
async def root():
    return {"message": "Cart Service API"}

@app.get("/cart/", response_model=Cart)
async def get_cart(request: Request):
    """Получение текущей корзины пользователя"""
    user_id = get_user_id(request)
    return get_or_create_cart(user_id)

@app.post("/cart/items", response_model=Cart)
async def add_item_to_cart(
    item: CartItemCreate, 
    request: Request, 
    product_api: httpx.AsyncClient = Depends(get_product_api_client)
):
    """Добавление товара в корзину"""
    user_id = get_user_id(request)
    cart = get_or_create_cart(user_id)
    
    # Проверяем наличие товара и его количество
    try:
        response = await product_api.get(f"/products/{item.product_id}")
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        
        product = response.json()
        if product["quantity"] < item.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough quantity for product {item.product_id}")
        
        # Проверяем, есть ли уже такой товар в корзине
        for cart_item in cart.items:
            if str(cart_item.product_id) == str(item.product_id):
                # Обновляем количество существующего товара
                cart_item.quantity += item.quantity
                # Пересчитываем общую стоимость корзины
                cart.total_price = sum(float(item.price) * item.quantity for item in cart.items)
                return cart
        
        # Добавляем новый товар в корзину
        cart_item = CartItem(
            product_id=item.product_id,
            quantity=item.quantity,
            price=float(product["price"]),
            product_name=product["name"]
        )
        cart.items.append(cart_item)
        
        # Пересчитываем общую стоимость корзины
        cart.total_price = sum(float(item.price) * item.quantity for item in cart.items)
        
        return cart
    
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Product service unavailable")

@app.put("/cart/items/{item_id}", response_model=Cart)
async def update_cart_item(
    item_id: UUID, 
    item_update: CartItemUpdate, 
    request: Request,
    product_api: httpx.AsyncClient = Depends(get_product_api_client)
):
    """Изменение количества товара в корзине"""
    user_id = get_user_id(request)
    
    if user_id not in carts_db:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    cart = carts_db[user_id]
    
    # Находим товар в корзине
    for cart_item in cart.items:
        if cart_item.id == item_id:
            # Проверяем наличие товара в нужном количестве
            try:
                response = await product_api.get(f"/products/{cart_item.product_id}")
                if response.status_code != 200:
                    raise HTTPException(status_code=404, detail=f"Product {cart_item.product_id} not found")
                
                product = response.json()
                if product["quantity"] < item_update.quantity:
                    raise HTTPException(status_code=400, detail=f"Not enough quantity for product {cart_item.product_id}")
                
                # Обновляем количество товара
                cart_item.quantity = item_update.quantity
                
                # Пересчитываем общую стоимость корзины
                cart.total_price = sum(float(item.price) * item.quantity for item in cart.items)
                
                return cart
            
            except httpx.RequestError:
                raise HTTPException(status_code=503, detail="Product service unavailable")
    
    raise HTTPException(status_code=404, detail="Item not found in cart")

@app.delete("/cart/items/{item_id}", response_model=Cart)
async def remove_cart_item(item_id: UUID, request: Request):
    """Удаление товара из корзины"""
    user_id = get_user_id(request)
    
    if user_id not in carts_db:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    cart = carts_db[user_id]
    
    # Находим и удаляем товар из корзины
    for i, cart_item in enumerate(cart.items):
        if cart_item.id == item_id:
            cart.items.pop(i)
            
            # Пересчитываем общую стоимость корзины
            cart.total_price = sum(float(item.price) * item.quantity for item in cart.items)
            
            return cart
    
    raise HTTPException(status_code=404, detail="Item not found in cart")

@app.get("/cart/total")
async def get_cart_total(request: Request):
    """Получение общей стоимости корзины"""
    user_id = get_user_id(request)
    cart = get_or_create_cart(user_id)
    
    return {"total_price": cart.total_price}

@app.post("/cart/checkout")
async def checkout_cart(
    request: Request, 
    order_api: httpx.AsyncClient = Depends(lambda: httpx.AsyncClient(base_url=f"http://{os.getenv('ORDER_SERVICE_HOST', 'order-service')}"))
):
    """Оформление заказа из корзины"""
    user_id = get_user_id(request)
    
    if user_id not in carts_db or not carts_db[user_id].items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    cart = carts_db[user_id]
    
    # Отправляем запрос в сервис заказов
    try:
        # Передаем заголовок X-User-ID для идентификации пользователя
        headers = {"X-User-ID": user_id}
        if "X-Token" in request.headers:
            headers["X-Token"] = request.headers["X-Token"]
        
        response = await order_api.post(
            "/orders/",
            json={
                "user_id": user_id,
                "items": [
                    {
                        "product_id": str(item.product_id),
                        "quantity": item.quantity,
                        "price": item.price,
                        "product_name": item.product_name
                    } for item in cart.items
                ],
                "total_price": cart.total_price
            },
            headers=headers
        )
        
        if response.status_code != 201:
            raise HTTPException(status_code=response.status_code, detail="Failed to create order")
        
        # Очищаем корзину
        cart.items = []
        cart.total_price = 0.0
        
        return response.json()
    
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Order service unavailable")

@app.delete("/cart/")
async def clear_cart(request: Request):
    """Очистка корзины"""
    user_id = get_user_id(request)
    
    if user_id in carts_db:
        cart = carts_db[user_id]
        cart.items = []
        cart.total_price = 0.0
    
    return {"message": "Cart cleared"}

@app.get("/carts/", response_model=List[Cart])
async def get_all_carts(request: Request, skip: int = 0, limit: int = 100):
    """Получение всех корзин (только для администраторов)"""
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return list(carts_db.values())[skip:skip+limit] 