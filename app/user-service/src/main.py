import os
import httpx
from fastapi import FastAPI, HTTPException, Depends, Request, Form, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt

# Настройки безопасности
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"  # В реальном приложении должен храниться в переменных окружения
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Модели данных
class UserBase(BaseModel):
    username: str
    full_name: Optional[str] = None
    phone: Optional[str] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.now)
    total_spent: float = 0.0

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class OrderSummary(BaseModel):
    id: UUID
    total_price: float
    status: str
    created_at: datetime

class UserProfile(User):
    orders: List[OrderSummary] = []
    current_cart_total: float = 0.0

# Хранилище пользователей (в памяти для примера)
# Структура: {username: UserInDB}
users_db: Dict[str, UserInDB] = {}

# Инструменты для работы с паролями и токенами
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Создание приложения FastAPI
app = FastAPI(
    title="User Service API",
    description="Сервис для управления пользователями",
    version="0.1.0",
)

# Вспомогательные функции
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(username: str):
    if username in users_db:
        return users_db[username]
    return None

def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

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
    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)):
    return current_user

# Клиенты для взаимодействия с другими сервисами
async def get_cart_api_client():
    async with httpx.AsyncClient(base_url=f"http://{os.getenv('CART_SERVICE_HOST', 'cart-service')}") as client:
        yield client

async def get_order_api_client():
    async with httpx.AsyncClient(base_url=f"http://{os.getenv('ORDER_SERVICE_HOST', 'order-service')}") as client:
        yield client

# Эндпоинты
@app.get("/")
async def root():
    return {"message": "User Service API"}

@app.post("/users/register", response_model=User)
async def register_user(user: UserCreate):
    """Регистрация нового пользователя"""
    if user.username in users_db:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    user_in_db = UserInDB(
        **user.dict(exclude={"password"}),
        hashed_password=hashed_password
    )
    users_db[user.username] = user_in_db
    
    return user_in_db

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Аутентификация пользователя и получение токена"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
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
            current_cart_total = cart_data.get("total_price", 0.0)
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
                    total_price=order["total_price"],
                    status=order["status"],
                    created_at=order["created_at"]
                )
                for order in orders_data
            ]
        else:
            orders = []
    except httpx.RequestError:
        orders = []
    
    # Создаем профиль пользователя
    profile = UserProfile(
        **current_user.dict(exclude={"hashed_password"}),
        orders=orders,
        current_cart_total=current_cart_total
    )
    
    return profile

@app.put("/users/me", response_model=User)
async def update_user(
    full_name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Обновление информации о пользователе"""
    if full_name is not None:
        current_user.full_name = full_name
    if phone is not None:
        current_user.phone = phone
    
    users_db[current_user.username] = current_user
    return current_user

@app.get("/users/me/orders", response_model=List[OrderSummary])
async def get_user_orders(
    current_user: UserInDB = Depends(get_current_active_user),
    order_api: httpx.AsyncClient = Depends(get_order_api_client)
):
    """Получение списка заказов пользователя"""
    try:
        response = await order_api.get("/orders/", headers={"X-User-ID": current_user.username})
        if response.status_code == 200:
            orders_data = response.json()
            orders = [
                OrderSummary(
                    id=order["id"],
                    total_price=order["total_price"],
                    status=order["status"],
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
            current_user.total_spent += order_data.get("total_price", 0.0)
            users_db[current_user.username] = current_user
            
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to create order")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Cart service unavailable")

@app.get("/users/me/total-spent")
async def get_total_spent(current_user: UserInDB = Depends(get_current_active_user)):
    """Получение общей суммы потраченных средств"""
    return {"total_spent": current_user.total_spent}

# Добавим тестового пользователя для демонстрации
@app.on_event("startup")
async def startup_event():
    # Создаем тестового пользователя
    if "testuser" not in users_db:
        hashed_password = get_password_hash("password123")
        users_db["testuser"] = UserInDB(
            username="testuser",
            full_name="Test User",
            phone="+7 (999) 123-45-67",
            hashed_password=hashed_password
        )
    
    # Создаем тестового администратора
    if "admin" not in users_db:
        hashed_password = get_password_hash("admin123")
        users_db["admin"] = UserInDB(
            username="admin",
            full_name="Administrator",
            phone="+7 (999) 999-99-99",
            hashed_password=hashed_password
        ) 