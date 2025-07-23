import os
import httpx
from fastapi import FastAPI, HTTPException, Depends, status, Form, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
import logging


# 1. Импортируем Instrumentator и Counter
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter


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
        total_spent=0.0
    )
    users_db[username] = user_in_db
    
    # Создаем токен для пользователя
    access_token_expires = timedelta(days=30)
    access_token = create_access_token(
        data={"sub": username}, expires_delta=access_token_expires
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
async def register_user(user: UserCreate):
    """Регистрация нового пользователя"""
    if user.username in users_db:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    user_in_db = UserInDB(
        username=user.username,
        full_name=user.full_name,
        phone=user.phone,
        hashed_password=hashed_password,
        id=f"{len(users_db) + 1:08d}",
        created_at=datetime.now(),
        total_spent=0.0
    )
    users_db[user.username] = user_in_db
    

    # Увеличиваем наш кастомный счетчик
    users_registered_counter.inc()


    return user_in_db

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Аутентификация пользователя и получение токена"""
    user = users_db.get(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
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
    try:
        # Создаем токен для аутентификации в сервисе заказов
        access_token = create_access_token(data={"sub": current_user.username})
        
        # Отправляем запрос с токеном для аутентификации
        response = await order_api.get(
            "/orders/", 
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-User-ID": current_user.username
            }
        )
        
        if response.status_code == 200:
            orders_data = response.json()
            orders = [
                OrderSummary(
                    id=order["id"],
                    status=order["status"],
                    total=order["total"],
                    created_at=order["created_at"]
                )
                for order in orders_data
            ]
            return orders
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to get orders")
    except httpx.RequestError:
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
    try:
        response = await cart_api.post("/cart/checkout", headers={"X-User-ID": current_user.username})
        if response.status_code == 200:
            # Обновляем общую сумму потраченных средств пользователя
            order_data = response.json()
            current_user.total_spent += order_data.get("total", 0.0)
            users_db[current_user.username] = current_user
            
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Failed to create order"))
    except httpx.RequestError as e:
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