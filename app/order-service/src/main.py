import os
import httpx
import asyncio
import random
from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks, Header
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta

# Модели данных
class OrderItem(BaseModel):
    product_id: str
    quantity: int
    price: float
    product_name: str

class OrderCreate(BaseModel):
    user_id: str
    items: List[OrderItem]
    total_price: float

class Order(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: str
    items: List[OrderItem]
    total_price: float
    status: str = "new"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    estimated_delivery: Optional[datetime] = None

# Статусы заказа
ORDER_STATUSES = ["new", "processing", "preparing", "shipping", "delivered", "cancelled"]

# Хранилище заказов (в памяти для примера)
# Структура: {order_id: Order}
orders_db: Dict[UUID, Order] = {}

# Создание приложения FastAPI
app = FastAPI(
    title="Order Service API",
    description="Сервис для управления заказами",
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

# Проверка авторизации (опционально)
async def verify_token(x_token: Optional[str] = Header(None)):
    if x_token is None:
        return None
    # В реальном приложении здесь была бы проверка токена через сервис пользователей
    return x_token

# Функция для автоматического обновления статуса заказа
async def process_order(order_id: UUID):
    # Получаем заказ
    if order_id not in orders_db:
        return
    
    order = orders_db[order_id]
    
    # Генерируем случайное время для каждого статуса (от 1 до 5 минут)
    # Для демонстрации используем секунды вместо минут
    processing_time = random.randint(10, 30)  # 10-30 секунд
    preparing_time = random.randint(10, 30)   # 10-30 секунд
    shipping_time = random.randint(10, 30)    # 10-30 секунд
    
    total_time = processing_time + preparing_time + shipping_time
    
    # Устанавливаем ожидаемое время доставки
    order.estimated_delivery = datetime.now() + timedelta(seconds=total_time)
    orders_db[order_id] = order
    
    # Статус "processing"
    await asyncio.sleep(processing_time)
    if order_id not in orders_db or orders_db[order_id].status == "cancelled":
        return
    
    order = orders_db[order_id]
    order.status = "processing"
    order.updated_at = datetime.now()
    orders_db[order_id] = order
    
    # Статус "preparing"
    await asyncio.sleep(preparing_time)
    if order_id not in orders_db or orders_db[order_id].status == "cancelled":
        return
    
    order = orders_db[order_id]
    order.status = "preparing"
    order.updated_at = datetime.now()
    orders_db[order_id] = order
    
    # Статус "shipping"
    await asyncio.sleep(shipping_time)
    if order_id not in orders_db or orders_db[order_id].status == "cancelled":
        return
    
    order = orders_db[order_id]
    order.status = "shipping"
    order.updated_at = datetime.now()
    orders_db[order_id] = order
    
    # Статус "delivered"
    await asyncio.sleep(10)  # Небольшая задержка для демонстрации
    if order_id not in orders_db or orders_db[order_id].status == "cancelled":
        return
    
    order = orders_db[order_id]
    order.status = "delivered"
    order.updated_at = datetime.now()
    orders_db[order_id] = order
    
    # Удаление заказа через некоторое время после доставки
    await asyncio.sleep(60)  # 1 минута для демонстрации
    if order_id in orders_db and orders_db[order_id].status == "delivered":
        del orders_db[order_id]

# Функция для уведомления сервиса пользователей об изменениях в заказе
async def notify_user_service(order_id: UUID, user_id: str):
    # В реальном приложении здесь был бы запрос к сервису пользователей
    # для обновления информации о заказе пользователя
    try:
        async with httpx.AsyncClient(base_url=f"http://{os.getenv('USER_SERVICE_HOST', 'user-service')}") as client:
            await client.post(
                f"/users/{user_id}/orders/{order_id}/update",
                json={"order_id": str(order_id), "status": orders_db[order_id].status if order_id in orders_db else "unknown"}
            )
    except Exception:
        # В случае ошибки просто логируем и продолжаем работу
        pass

# Эндпоинты
@app.get("/")
async def root():
    return {"message": "Order Service API"}

@app.post("/orders/", response_model=Order, status_code=201)
async def create_order(order_data: OrderCreate, request: Request, background_tasks: BackgroundTasks):
    """Создание нового заказа"""
    user_id = get_user_id(request)
    
    # Проверяем, что user_id в запросе совпадает с заголовком
    if order_data.user_id != user_id and not is_admin(request):
        raise HTTPException(status_code=403, detail="Cannot create order for another user")
    
    # Создаем заказ
    order = Order(
        user_id=order_data.user_id,
        items=order_data.items,
        total_price=order_data.total_price
    )
    
    orders_db[order.id] = order
    
    # Запускаем процесс обработки заказа в фоне
    background_tasks.add_task(process_order, order.id)
    
    # Уведомляем сервис пользователей о новом заказе
    background_tasks.add_task(notify_user_service, order.id, user_id)
    
    return order

@app.get("/orders/", response_model=List[Order])
async def list_orders(request: Request, skip: int = 0, limit: int = 100):
    """Получение списка заказов пользователя или всех заказов для админа"""
    user_id = get_user_id(request)
    
    if is_admin(request):
        # Для администратора возвращаем все заказы
        return list(orders_db.values())[skip:skip+limit]
    else:
        # Для обычного пользователя возвращаем только его заказы
        user_orders = [order for order in orders_db.values() if order.user_id == user_id]
        return user_orders[skip:skip+limit]

@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: UUID, request: Request):
    """Получение информации о конкретном заказе"""
    user_id = get_user_id(request)
    
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = orders_db[order_id]
    
    # Проверяем, что пользователь имеет доступ к заказу
    if order.user_id != user_id and not is_admin(request):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return order

@app.put("/orders/{order_id}/status")
async def update_order_status(order_id: UUID, status: str, request: Request, background_tasks: BackgroundTasks):
    """Обновление статуса заказа (только для администраторов)"""
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(ORDER_STATUSES)}")
    
    order = orders_db[order_id]
    order.status = status
    order.updated_at = datetime.now()
    orders_db[order_id] = order
    
    # Уведомляем сервис пользователей об изменении статуса заказа
    background_tasks.add_task(notify_user_service, order_id, order.user_id)
    
    return {"message": f"Order status updated to {status}"}

@app.put("/orders/{order_id}/cancel")
async def cancel_order(order_id: UUID, request: Request, background_tasks: BackgroundTasks):
    """Отмена заказа"""
    user_id = get_user_id(request)
    
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = orders_db[order_id]
    
    # Проверяем, что пользователь имеет доступ к заказу
    if order.user_id != user_id and not is_admin(request):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Проверяем, что заказ можно отменить
    if order.status in ["delivered", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel order with status {order.status}")
    
    order.status = "cancelled"
    order.updated_at = datetime.now()
    orders_db[order_id] = order
    
    # Уведомляем сервис пользователей об отмене заказа
    background_tasks.add_task(notify_user_service, order_id, user_id)
    
    return {"message": "Order cancelled"}

@app.get("/orders/statuses/list")
async def get_order_statuses():
    """Получение списка возможных статусов заказа"""
    return {"statuses": ORDER_STATUSES} 