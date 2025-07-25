import os
import httpx
import asyncio
import random
from jose import JWTError, jwt
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from pydantic import BaseModel, UUID4
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime
import logging

# 1. Импорт необходимых классов из prometheus_client
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram

# Импортируем модуль трейсинга
from src.tracing import setup_tracing, get_tracer

app = FastAPI()

# Инициализация OpenTelemetry трейсинга
tracer = setup_tracing(app)
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 2. Инструментация приложения с исключенным эндпоинтом /health
# Это не позволит быстрым ответам от health check влиять на общую метрику p99
instrumentator = Instrumentator(excluded_handlers=["/health"]).instrument(app).expose(app)

# 3. Определение кастомных метрик
ORDERS_CREATED_TOTAL = Counter(
    'orders_created_total',
    'Total number of created orders'
)

ORDERS_STATUS_TOTAL = Counter(
    'orders_status_total',
    'Total number of orders by status',
    ['status']  # Метка для разделения по статусам
)

ORDER_DELIVERY_DURATION_SECONDS = Histogram(
    'order_delivery_duration_seconds',
    'Time from order creation to delivery in seconds',
    buckets=[30, 60, 120, 180, 240, 300, 360, 480, 600] # Бакеты от 30с до 10 мин
)


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

async def process_order(order_id: str, background_tasks: BackgroundTasks):
    with tracer.start_as_current_span("process_order") as span:
        span.set_attribute("order.id", order_id)
        
        if order_id not in orders_db:
            span.set_attribute("error", "order_not_found")
            return
        
        order = orders_db[order_id]
        span.set_attribute("order.status.initial", order["status"])
        span.set_attribute("user.id", order["user_id"])

        await asyncio.sleep(5)
        if order_id in orders_db and order["status"] != "CANCELLED":
            order["status"] = "PROCESSING"
            order["updated_at"] = datetime.now().isoformat()
            span.set_attribute("order.status.new", "PROCESSING")
            # 4. Инкремент метрики статуса
            ORDERS_STATUS_TOTAL.labels(status='PROCESSING').inc()
            await notify_user_service(order_id, "PROCESSING")

        await asyncio.sleep(5)
        if order_id in orders_db and order["status"] != "CANCELLED":
            order["status"] = "SHIPPING"
            order["updated_at"] = datetime.now().isoformat()
            span.set_attribute("order.status.new", "SHIPPING")
            # 4. Инкремент метрики статуса
            ORDERS_STATUS_TOTAL.labels(status='SHIPPING').inc()
            await notify_user_service(order_id, "SHIPPING")
        
        delivery_time = random.randint(60, 300)
        span.set_attribute("order.delivery.time.seconds", delivery_time)
        await asyncio.sleep(delivery_time)
        
        if order_id in orders_db and order["status"] != "CANCELLED":
            order["status"] = "DELIVERED"
            order["updated_at"] = datetime.now().isoformat()
            span.set_attribute("order.status.new", "DELIVERED")
            # 4. Инкремент метрики статуса
            ORDERS_STATUS_TOTAL.labels(status='DELIVERED').inc()
            
            # 5. Расчет и запись времени доставки
            try:
                created_at = datetime.fromisoformat(order["created_at"])
                delivered_at = datetime.fromisoformat(order["updated_at"])
                duration = (delivered_at - created_at).total_seconds()
                span.set_attribute("order.delivery.duration.seconds", duration)
                ORDER_DELIVERY_DURATION_SECONDS.observe(duration)
            except (ValueError, TypeError) as e:
                span.set_attribute("error", "delivery_duration_calculation_failed")
                span.set_attribute("error.message", str(e))
                logger.error(f"Could not calculate delivery duration for order {order_id}")

            await notify_user_service(order_id, "DELIVERED")
            background_tasks.add_task(delete_order_after_delay, order_id, 300)

async def delete_order_after_delay(order_id: str, delay: int):
    with tracer.start_as_current_span("delete_order_after_delay") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("delay.seconds", delay)
        
        await asyncio.sleep(delay)
        if order_id in orders_db:
            del orders_db[order_id]
            span.set_attribute("deleted", True)
            logger.info(f"Order {order_id} deleted from in-memory DB after delivery.")

async def notify_user_service(order_id: str, status: str):
    with tracer.start_as_current_span("notify_user_service") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("order.status", status)
        
        if order_id not in orders_db:
            span.set_attribute("error", "order_not_found")
            return
        
        try:
            order = orders_db[order_id]
            span.set_attribute("user.id", order["user_id"])
            
            async with httpx.AsyncClient() as client:
                with tracer.start_as_current_span("user_service_notification_request") as req_span:
                    req_span.set_attribute("http.method", "POST")
                    req_span.set_attribute("http.url", f"{USER_SERVICE_URL}/users/notify/order-status")
                    
                    response = await client.post(
                        f"{USER_SERVICE_URL}/users/notify/order-status",
                        json={ "order_id": order_id, "user_id": order["user_id"], "status": status, "updated_at": order["updated_at"] }
                    )
                    req_span.set_attribute("http.status_code", response.status_code)
        except httpx.RequestError as e:
            span.set_attribute("error", "request_error")
            span.set_attribute("error.message", str(e))
            logger.error(f"Failed to notify user service for order {order_id}: {e}")

# Маршруты API
@app.get("/")
async def root():
    return {"message": "Order Service API"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "order-service"}

@app.get("/orders/", response_model=List[Order])
async def get_orders(user_id: str = Depends(get_user_id), admin: Optional[bool] = Header(False)):
    with tracer.start_as_current_span("get_orders") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("admin.access", admin)
        
        if admin:
            span.set_attribute("orders.count", len(orders_db))
            return [order for order in orders_db.values()]
        
        user_orders = [order for order in orders_db.values() if order["user_id"] == user_id]
        span.set_attribute("orders.count", len(user_orders))
        return user_orders

@app.post("/orders/", response_model=Order)
async def create_order(order: OrderCreate, background_tasks: BackgroundTasks, user_id: str = Depends(get_user_id)):
    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("order.items.count", len(order.items))
        span.set_attribute("order.total", order.total)
        
        order_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        try:
            if user_id.count('.') == 2:
                payload = jwt.decode(user_id, SECRET_KEY, algorithms=[ALGORITHM])
                username = payload.get("sub")
                if username:
                    user_id = username
                    span.set_attribute("user.id.jwt_decoded", username)
        except Exception as e:
            span.set_attribute("error", "jwt_decode_error")
            span.set_attribute("error.message", str(e))
        
        new_order = {
            "id": order_id, "user_id": user_id, "items": [dict(item) for item in order.items],
            "total": order.total, "status": "CREATED", "created_at": now, "updated_at": now
        }
        
        orders_db[order_id] = new_order
        span.set_attribute("order.id", order_id)
        
        # 6. Инкремент метрик при создании заказа
        ORDERS_CREATED_TOTAL.inc()
        ORDERS_STATUS_TOTAL.labels(status='CREATED').inc()
        
        background_tasks.add_task(process_order, order_id, background_tasks)
        return new_order

@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str, user_id: str = Depends(get_user_id), admin: Optional[bool] = Header(False)):
    with tracer.start_as_current_span("get_order") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("user.id", user_id)
        span.set_attribute("admin.access", admin)
        
        if order_id not in orders_db:
            span.set_attribute("error", "order_not_found")
            raise HTTPException(status_code=404, detail="Order not found")
        
        order = orders_db[order_id]
        if order["user_id"] != user_id and not admin:
            span.set_attribute("error", "access_denied")
            raise HTTPException(status_code=403, detail="Access denied")
        
        return order

@app.put("/orders/{order_id}/status")
async def update_order_status(order_id: str, status: str, background_tasks: BackgroundTasks, admin: Optional[bool] = Header(False)):
    with tracer.start_as_current_span("update_order_status") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("order.status.new", status)
        span.set_attribute("admin.access", admin)
        
        if not admin:
            span.set_attribute("error", "admin_access_required")
            raise HTTPException(status_code=403, detail="Admin access required")
        if order_id not in orders_db:
            span.set_attribute("error", "order_not_found")
            raise HTTPException(status_code=404, detail="Order not found")
        if status not in ORDER_STATUSES:
            span.set_attribute("error", "invalid_status")
            raise HTTPException(status_code=400, detail=f"Invalid status. Available statuses: {', '.join(ORDER_STATUSES.keys())}")
        
        orders_db[order_id]["status"] = status
        orders_db[order_id]["updated_at"] = datetime.now().isoformat()
        
        # 7. Инкремент метрики при ручном обновлении статуса
        ORDERS_STATUS_TOTAL.labels(status=status).inc()
        
        background_tasks.add_task(notify_user_service, order_id, status)
        return {"message": f"Order status updated to {status}"}

@app.put("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, user_id: str = Depends(get_user_id), admin: Optional[bool] = Header(False)):
    with tracer.start_as_current_span("cancel_order") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("user.id", user_id)
        span.set_attribute("admin.access", admin)
        
        if order_id not in orders_db:
            span.set_attribute("error", "order_not_found")
            raise HTTPException(status_code=404, detail="Order not found")
        
        order = orders_db[order_id]
        if order["user_id"] != user_id and not admin:
            span.set_attribute("error", "access_denied")
            raise HTTPException(status_code=403, detail="Access denied")
        
        if order["status"] in ["DELIVERED", "CANCELLED"]:
            span.set_attribute("error", "invalid_status_transition")
            raise HTTPException(status_code=400, detail=f"Cannot cancel order with status {order['status']}")
        
        order["status"] = "CANCELLED"
        order["updated_at"] = datetime.now().isoformat()
        span.set_attribute("order.status.new", "CANCELLED")
        
        # 7. Инкремент метрики при отмене
        ORDERS_STATUS_TOTAL.labels(status='CANCELLED').inc()
        
        asyncio.create_task(notify_user_service(order_id, "CANCELLED"))
        return {"message": "Order cancelled", "order": order}

@app.get("/orders/statuses/list")
async def get_order_statuses():
    with tracer.start_as_current_span("get_order_statuses"):
        return ORDER_STATUSES