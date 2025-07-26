import os
import httpx
from fastapi import FastAPI, HTTPException, Depends, status, Form, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
import logging

# 1. Импортируем Instrumentator и Counter
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter


# Импортируем модуль трейсинга
from src.tracing import setup_tracing, get_tracer

# Импортируем модуль профилирования
from src.profiling import profile_endpoint, profile_context, get_profile_stats, list_available_profiles


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Настройки
SECRET_KEY = os.environ.get("SECRET_KEY", "supersecretkey123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
CART_SERVICE_URL = os.environ.get("CART_SERVICE_URL", "http://cart-service:8001")
ORDER_SERVICE_URL = os.environ.get("ORDER_SERVICE_URL", "http://order-service:8002")

# Создание приложения FastAPI
app = FastAPI()

# Инициализация OpenTelemetry трейсинга
tracer = setup_tracing(app)
logger.info("Tracing initialized for User Service")

# Настройка CORS для поддержки запросов из браузера
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене следует указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Создаем кастомную метрику для подсчета регистраций
users_registered_counter = Counter(
    'users_registered_total',
    'Total number of users registered'
)

# 3. Инструментируем приложение с Prometheus при создании
instrumentator = Instrumentator().instrument(app).expose(app)


# Модели данных
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str
    full_name: str
    phone: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: str
    created_at: datetime
    total_spent: float = 0.0
    is_admin: bool = False

class UserInDB(User):
    hashed_password: str

class OrderSummary(BaseModel):
    id: str
    status: str
    total: float
    created_at: str

class UserProfile(User):
    current_cart_total: float
    orders: List[OrderSummary]

# In-memory хранилище пользователей
users_db: Dict[str, UserInDB] = {}

# Настройка безопасности
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Функции для работы с паролями и токенами
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Функция для создания пользователя
def create_user(username: str, password: str, full_name: str, phone: str, is_admin: bool = False) -> UserInDB:
    if username in users_db:
        return users_db[username]
    
    hashed_password = get_password_hash(password)
    user_in_db = UserInDB(
        username=username,
        full_name=full_name,
        phone=phone,
        hashed_password=hashed_password,
        id=f"{len(users_db) + 1:08d}",
        created_at=datetime.now(),
        total_spent=0.0,
        is_admin=is_admin
    )
    users_db[username] = user_in_db
    
    # Создаем токен для пользователя с информацией о роли
    access_token_expires = timedelta(days=30)
    access_token = create_access_token(
        data={"sub": username, "is_admin": is_admin}, expires_delta=access_token_expires
    )
    
    # Логируем информацию о созданном пользователе
    admin_status = "ADMIN USER" if is_admin else "REGULAR USER"
    logger.info(f"Created {admin_status}: {username}")
    logger.info(f"Username: {username}")
    logger.info(f"Password: {password}")
    logger.info(f"Access Token: {access_token}")
    
    return user_in_db

# Создаем демо пользователей при запуске
@app.on_event("startup")
async def startup_event():
    logger.info("Application instrumented for Prometheus with default settings")

    logger.info("Creating default users for Swagger UI...")
    
    # Создаем обычного пользователя
    create_user(
        username="swagger_user",
        password="password123",
        full_name="Swagger Regular User",
        phone="+7 (999) 123-45-67"
    )
    
    # Создаем пользователя с правами администратора
    create_user(
        username="swagger_admin",
        password="admin123",
        full_name="Swagger Admin User",
        phone="+7 (999) 987-65-43",
        is_admin=True
    )
    
    logger.info("Default users created successfully!")

# Функции для работы с пользователями
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = users_db.get(token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)):
    return current_user

# Клиенты для других сервисов
async def get_cart_api_client():
    async with httpx.AsyncClient(base_url=CART_SERVICE_URL) as client:
        yield client

async def get_order_api_client():
    async with httpx.AsyncClient(base_url=ORDER_SERVICE_URL) as client:
        yield client

# Эндпоинты
@app.get("/")
async def root():
    return {"message": "User Service API"}

@app.get("/health")
async def health_check():
    """Health check эндпоинт для проверки состояния сервиса"""
    return {"status": "ok", "service": "user-service"}

@app.post("/users/register", response_model=User)
@profile_endpoint("user_registration")
async def register_user(user: UserCreate):
    """Регистрация нового пользователя"""
    with tracer.start_as_current_span("register_user") as span:
        # Добавляем атрибуты в span
        span.set_attribute("user.username", user.username)
        span.set_attribute("user.full_name", user.full_name)
        
        if user.username in users_db:
            span.set_attribute("registration.status", "failed")
            span.set_attribute("registration.error", "username_exists")
            raise HTTPException(status_code=400, detail="Username already registered")
        
        # Определяем, является ли пользователь админом на основе username
        is_admin = user.username.startswith("admin_")
        span.set_attribute("user.is_admin", is_admin)
        
        with tracer.start_as_current_span("password_hashing"):
            hashed_password = get_password_hash(user.password)
        
        with tracer.start_as_current_span("user_creation"):
            user_in_db = UserInDB(
                username=user.username,
                full_name=user.full_name,
                phone=user.phone,
                hashed_password=hashed_password,
                id=f"{len(users_db) + 1:08d}",
                created_at=datetime.now(),
                total_spent=0.0,
                is_admin=is_admin
            )
            span.set_attribute("user.id", user_in_db.id)
            users_db[user.username] = user_in_db
        

        # Увеличиваем наш кастомный счетчик
        users_registered_counter.inc()

        # Логируем информацию о созданном пользователе
        admin_status = "ADMIN USER" if is_admin else "REGULAR USER"
        logger.info(f"Registered {admin_status}: {user.username}")
        
        span.set_attribute("registration.status", "success")
        return user_in_db

@app.post("/token", response_model=Token)
@profile_endpoint("user_login")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Аутентификация пользователя и получение токена"""
    with tracer.start_as_current_span("login_for_access_token") as span:
        span.set_attribute("auth.username", form_data.username)
        
        with tracer.start_as_current_span("user_lookup"):
            user = users_db.get(form_data.username)
            span.set_attribute("user.found", user is not None)
        
        with tracer.start_as_current_span("password_verification") as verify_span:
            password_valid = user and verify_password(form_data.password, user.hashed_password)
            verify_span.set_attribute("password.valid", password_valid)
            
            if not password_valid:
                span.set_attribute("auth.status", "failed")
                span.set_attribute("auth.error", "invalid_credentials")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        
        # Теперь мы знаем, что user не None
        assert user is not None  # Type assertion для mypy
        with tracer.start_as_current_span("token_creation"):
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": user.username, "is_admin": user.is_admin}, expires_delta=access_token_expires
            )
            span.set_attribute("token.expires_minutes", ACCESS_TOKEN_EXPIRE_MINUTES)
            span.set_attribute("user.is_admin", user.is_admin)
        
        span.set_attribute("auth.status", "success")
        return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: UserInDB = Depends(get_current_active_user)):
    """Получение информации о текущем пользователе"""
    return current_user

@app.put("/users/me", response_model=User)
async def update_user(
    full_name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Обновление информации о пользователе"""
    if full_name:
        current_user.full_name = full_name
    if phone:
        current_user.phone = phone
    
    users_db[current_user.username] = current_user
    return current_user

@app.get("/users/me/profile", response_model=UserProfile)
@profile_endpoint("get_user_profile")
async def get_user_profile(
    current_user: UserInDB = Depends(get_current_active_user),
    cart_api: httpx.AsyncClient = Depends(get_cart_api_client),
    order_api: httpx.AsyncClient = Depends(get_order_api_client)
):
    """Получение профиля пользователя с информацией о заказах и корзине"""
    # Получаем текущую корзину пользователя
    try:
        cart_response = await cart_api.get("/cart/", headers={"X-User-ID": current_user.username})
        if cart_response.status_code == 200:
            cart_data = cart_response.json()
            current_cart_total = cart_data.get("total", 0.0)
        else:
            current_cart_total = 0.0
    except httpx.RequestError:
        current_cart_total = 0.0
    
    # Получаем заказы пользователя
    try:
        orders_response = await order_api.get("/orders/", headers={"X-User-ID": current_user.username})
        if orders_response.status_code == 200:
            orders_data = orders_response.json()
            orders = [
                OrderSummary(
                    id=order["id"],
                    status=order["status"],
                    total=order["total"],
                    created_at=order["created_at"]
                )
                for order in orders_data
            ]
        else:
            orders = []
    except httpx.RequestError:
        orders = []
    
    return UserProfile(
        **current_user.dict(),
        current_cart_total=current_cart_total,
        orders=orders
    )

@app.get("/users/me/orders", response_model=List[OrderSummary])
async def get_user_orders(
    current_user: UserInDB = Depends(get_current_active_user),
    order_api: httpx.AsyncClient = Depends(get_order_api_client)
):
    """Получение списка заказов пользователя"""
    with tracer.start_as_current_span("get_user_orders") as span:
        span.set_attribute("user.username", current_user.username)
        span.set_attribute("user.id", current_user.id)
        
        try:
            with tracer.start_as_current_span("create_service_token"):
                # Создаем токен для аутентификации в сервисе заказов
                access_token = create_access_token(data={"sub": current_user.username})
            
            with tracer.start_as_current_span("order_service_request") as req_span:
                req_span.set_attribute("http.method", "GET")
                req_span.set_attribute("http.url", "/orders/")
                req_span.set_attribute("service.name", "order-service")
                
                # Отправляем запрос с токеном для аутентификации
                response = await order_api.get(
                    "/orders/", 
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "X-User-ID": current_user.username
                    }
                )
                
                req_span.set_attribute("http.status_code", response.status_code)
            
            if response.status_code == 200:
                with tracer.start_as_current_span("process_orders_response"):
                    orders_data = response.json()
                    span.set_attribute("orders.count", len(orders_data))
                    orders = [
                        OrderSummary(
                            id=order["id"],
                            status=order["status"],
                            total=order["total"],
                            created_at=order["created_at"]
                        )
                        for order in orders_data
                    ]
                    span.set_attribute("operation.status", "success")
                    return orders
            else:
                span.set_attribute("operation.status", "failed")
                span.set_attribute("error.status_code", response.status_code)
                raise HTTPException(status_code=response.status_code, detail="Failed to get orders")
        except httpx.RequestError as e:
            span.set_attribute("operation.status", "error")
            span.set_attribute("error.type", "request_error")
            span.set_attribute("error.message", str(e))
            raise HTTPException(status_code=503, detail="Order service unavailable")

@app.get("/users/me/cart")
async def get_user_cart(
    current_user: UserInDB = Depends(get_current_active_user),
    cart_api: httpx.AsyncClient = Depends(get_cart_api_client)
):
    """Получение корзины пользователя"""
    try:
        response = await cart_api.get("/cart/", headers={"X-User-ID": current_user.username})
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to get cart")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Cart service unavailable")

@app.post("/users/me/orders")
async def create_order_from_cart(
    current_user: UserInDB = Depends(get_current_active_user),
    cart_api: httpx.AsyncClient = Depends(get_cart_api_client)
):
    """Оформление заказа из корзины пользователя"""
    with tracer.start_as_current_span("create_order_from_cart") as span:
        span.set_attribute("user.username", current_user.username)
        span.set_attribute("user.id", current_user.id)
        span.set_attribute("user.total_spent_before", current_user.total_spent)
        
        try:
            with tracer.start_as_current_span("cart_checkout_request") as req_span:
                req_span.set_attribute("http.method", "POST")
                req_span.set_attribute("http.url", "/cart/checkout")
                req_span.set_attribute("service.name", "cart-service")
                
                response = await cart_api.post("/cart/checkout", headers={"X-User-ID": current_user.username})
                req_span.set_attribute("http.status_code", response.status_code)
            
            if response.status_code == 200:
                with tracer.start_as_current_span("update_user_spending"):
                    # Обновляем общую сумму потраченных средств пользователя
                    order_data = response.json()
                    order_total = order_data.get("total", 0.0)
                    span.set_attribute("order.total", order_total)
                    
                    current_user.total_spent += order_total
                    users_db[current_user.username] = current_user
                    
                    span.set_attribute("user.total_spent_after", current_user.total_spent)
                    span.set_attribute("operation.status", "success")
                
                return response.json()
            else:
                span.set_attribute("operation.status", "failed")
                span.set_attribute("error.status_code", response.status_code)
                error_detail = response.json().get("detail", "Failed to create order")
                span.set_attribute("error.detail", error_detail)
                raise HTTPException(status_code=response.status_code, detail=error_detail)
        except httpx.RequestError as e:
            span.set_attribute("operation.status", "error")
            span.set_attribute("error.type", "request_error")
            span.set_attribute("error.message", str(e))
            raise HTTPException(status_code=503, detail=f"Cart service unavailable: {str(e)}")

@app.get("/users/me/total-spent")
async def get_total_spent(current_user: UserInDB = Depends(get_current_active_user)):
    """Получение общей суммы потраченных средств"""
    return {"total_spent": current_user.total_spent}

@app.post("/users/notify/order-status")
async def notify_order_status(order_update: dict):
    """Обработка уведомления об изменении статуса заказа"""
    # В реальном приложении здесь была бы логика обновления информации о заказе
    # и отправка уведомления пользователю
    return {"message": "Order status update received"}

# Эндпоинт для получения токена администратора (для Swagger UI)
@app.get("/swagger-admin-token")
async def get_swagger_admin_token():
    """Получение токена администратора для Swagger UI"""
    if "swagger_admin" not in users_db:
        raise HTTPException(status_code=404, detail="Swagger admin user not found")
    
    access_token_expires = timedelta(days=30)
    access_token = create_access_token(
        data={"sub": "swagger_admin"}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": "swagger_admin",
        "is_admin": True
    }

# Эндпоинты для управления профилированием
@app.get("/profiling/status")
async def get_profiling_status():
    """Получение статуса профилирования"""
    return {
        "enabled": os.environ.get("ENABLE_PROFILING", "false").lower() == "true",
        "profiles_directory": "/app/profiles"
    }

@app.get("/profiling/profiles")
async def list_profiles():
    """Получение списка доступных профилей"""
    return {"profiles": list_available_profiles()}

@app.get("/profiling/profiles/{filename}/stats")
async def get_profile_stats_endpoint(filename: str):
    """Получение статистики профиля"""
    profile_path = f"/app/profiles/{filename}"
    stats = get_profile_stats(profile_path)
    return {"filename": filename, "stats": stats}

@app.post("/profiling/manual/{operation_name}")
@profile_endpoint("manual_operation")
async def manual_profiling_test(operation_name: str):
    """Тестовый эндпоинт для ручного профилирования"""
    import time
    import random
    import asyncio
    
    # Имитация различных операций
    with profile_context(f"manual_{operation_name}"):
        # Имитация работы с данными
        data = []
        for i in range(1000):
            data.append(random.random() * i)
        
        # Имитация сортировки
        sorted_data = sorted(data, reverse=True)
        
        # Имитация IO операции
        await asyncio.sleep(0.1)
        
        return {
            "operation": operation_name,
            "processed_items": len(data),
            "max_value": max(sorted_data),
            "profiling_enabled": os.environ.get("ENABLE_PROFILING", "false").lower() == "true"
        }