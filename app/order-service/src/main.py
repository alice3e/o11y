import os
import httpx
import asyncio
import random
import jwt
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from pydantic import BaseModel, UUID4
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime

app = FastAPI()

# Настройки
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://user-service:8003")
SECRET_KEY = os.environ.get("SECRET_KEY", "supersecretkey123")
ALGORITHM = "HS256"

# Статусы заказа
ORDER_STATUSES = {
    "CREATED": "Создан",
    "PROCESSING": "Обрабатывается",
    "SHIPPING": "Доставляется",
    "DELIVERED": "Доставлен",
    "CANCELLED": "Отменен"
}

# In-memory хранилище заказов
orders_db: Dict[str, Dict[str, Any]] = {}

# Модели данных
class OrderItem(BaseModel):
    product_id: str
    name: str
    price: float
    quantity: int

class OrderCreate(BaseModel):
    items: List[OrderItem]
    total: float

class Order(BaseModel):
    id: str
    user_id: str
    items: List[OrderItem]
    total: float
    status: str
    created_at: str
    updated_at: str

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
    
    token = parts[1]
    
    # Пытаемся декодировать JWT для получения username
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username:
            return username
    except Exception:
        # Если не удалось декодировать, используем токен как идентификатор
        pass
    
    # Возвращаем токен как идентификатор пользователя
    return token

async def process_order(order_id: str, background_tasks: BackgroundTasks):
    """Фоновая задача для обработки заказа"""
    # Имитация процесса обработки заказа
    if order_id not in orders_db:
        return
    
    # Изменение статуса на "Обрабатывается"
    await asyncio.sleep(5)  # Имитация задержки
    if order_id in orders_db and orders_db[order_id]["status"] != "CANCELLED":
        orders_db[order_id]["status"] = "PROCESSING"
        orders_db[order_id]["updated_at"] = datetime.now().isoformat()
        await notify_user_service(order_id, "PROCESSING")
    
    # Изменение статуса на "Доставляется"
    await asyncio.sleep(5)  # Имитация задержки
    if order_id in orders_db and orders_db[order_id]["status"] != "CANCELLED":
        orders_db[order_id]["status"] = "SHIPPING"
        orders_db[order_id]["updated_at"] = datetime.now().isoformat()
        await notify_user_service(order_id, "SHIPPING")
    
    # Случайная задержка от 1 до 5 минут (для тестирования используем секунды)
    delivery_time = random.randint(60, 300)
    await asyncio.sleep(delivery_time)  # Имитация задержки
    
    # Изменение статуса на "Доставлен"
    if order_id in orders_db and orders_db[order_id]["status"] != "CANCELLED":
        orders_db[order_id]["status"] = "DELIVERED"
        orders_db[order_id]["updated_at"] = datetime.now().isoformat()
        await notify_user_service(order_id, "DELIVERED")
        
        # Удаление заказа через 5 минут после доставки
        background_tasks.add_task(delete_order_after_delay, order_id, 300)

async def delete_order_after_delay(order_id: str, delay: int):
    """Удаление заказа после указанной задержки"""
    await asyncio.sleep(delay)
    if order_id in orders_db:
        del orders_db[order_id]

async def notify_user_service(order_id: str, status: str):
    """Уведомление сервиса пользователей об изменении статуса заказа"""
    if order_id not in orders_db:
        return
    
    try:
        order = orders_db[order_id]
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{USER_SERVICE_URL}/users/notify/order-status",
                json={
                    "order_id": order_id,
                    "user_id": order["user_id"],
                    "status": status,
                    "updated_at": order["updated_at"]
                }
            )
    except httpx.RequestError:
        # Логирование ошибки (в реальном приложении)
        pass

# Маршруты API
@app.get("/")
async def root():
    return {"message": "Order Service API"}

@app.get("/orders/", response_model=List[Order])
async def get_orders(user_id: str = Depends(get_user_id), admin: Optional[bool] = Header(False)):
    """Получение списка заказов пользователя или всех заказов для админа"""
    if admin:
        # Для администратора возвращаем все заказы
        return [order for order in orders_db.values()]
    
    # Для обычного пользователя возвращаем только его заказы
    return [order for order in orders_db.values() if order["user_id"] == user_id]

@app.post("/orders/", response_model=Order)
async def create_order(
    order: OrderCreate, 
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_user_id)
):
    """Создание нового заказа"""
    order_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    # Извлекаем username из JWT токена, если это токен
    try:
        if user_id.count('.') == 2:  # Простая проверка, что это может быть JWT
            payload = jwt.decode(user_id, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username:
                user_id = username
    except Exception:
        # Если не удалось декодировать, используем user_id как есть
        pass
    
    new_order = {
        "id": order_id,
        "user_id": user_id,
        "items": [dict(item) for item in order.items],
        "total": order.total,
        "status": "CREATED",
        "created_at": now,
        "updated_at": now
    }
    
    orders_db[order_id] = new_order
    
    # Запускаем фоновую задачу для обработки заказа
    background_tasks.add_task(process_order, order_id, background_tasks)
    
    return new_order

@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str, user_id: str = Depends(get_user_id), admin: Optional[bool] = Header(False)):
    """Получение информации о заказе"""
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = orders_db[order_id]
    
    # Проверяем права доступа
    if order["user_id"] != user_id and not admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return order

@app.put("/orders/{order_id}/status")
async def update_order_status(
    order_id: str, 
    status: str, 
    background_tasks: BackgroundTasks,
    admin: Optional[bool] = Header(False)
):
    """Обновление статуса заказа (только для администраторов)"""
    if not admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Available statuses: {', '.join(ORDER_STATUSES.keys())}")
    
    orders_db[order_id]["status"] = status
    orders_db[order_id]["updated_at"] = datetime.now().isoformat()
    
    # Уведомляем сервис пользователей об изменении статуса
    background_tasks.add_task(notify_user_service, order_id, status)
    
    return {"message": f"Order status updated to {status}"}

@app.put("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, user_id: str = Depends(get_user_id), admin: Optional[bool] = Header(False)):
    """Отмена заказа"""
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = orders_db[order_id]
    
    # Проверяем права доступа
    if order["user_id"] != user_id and not admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Проверяем, можно ли отменить заказ
    if order["status"] in ["DELIVERED", "CANCELLED"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel order with status {order['status']}")
    
    # Обновляем статус заказа
    order["status"] = "CANCELLED"
    order["updated_at"] = datetime.now().isoformat()
    
    # Уведомляем сервис пользователей об отмене заказа
    asyncio.create_task(notify_user_service(order_id, "CANCELLED"))
    
    return {"message": "Order cancelled", "order": order}

@app.get("/orders/statuses/list")
async def get_order_statuses():
    """Получение списка возможных статусов заказа"""
    return ORDER_STATUSES 