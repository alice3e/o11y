# 🔐 Аутентификация и авторизация

Надежная система безопасности для микросервисной архитектуры Product Store с JWT токенами, ролевой моделью и защищенным межсервисным взаимодействием.

## 🎫 JWT-аутентификация

Система использует **JSON Web Tokens (JWT)** как основной механизм аутентификации:

### ✅ Преимущества JWT
- **🔒 Безопасность**: Токены подписываются секретным ключом HS256
- **⚡ Без состояния**: Серверу не нужно хранить сессии
- **📈 Масштабируемость**: Идеально для микросервисов
- **📦 Встроенные данные**: Токен содержит роль пользователя

### 🏗️ Структура токена

```json
{
  "sub": "username",           # Имя пользователя (subject)
  "is_admin": true,           # Флаг администратора
  "exp": 1690311600           # Время истечения (Unix timestamp)
}
```

**Конфигурация:**
- **Алгоритм**: `HS256`
- **Время жизни**: 30 минут (настраивается)
- **Секретный ключ**: `supersecretkey123` (одинаковый для всех сервисов)

---

## 🔄 Процесс аутентификации

### 1. 📝 Регистрация пользователя

```http
POST /user-api/users/register
Content-Type: application/json

{
  "username": "newuser",
  "full_name": "New User",
  "phone": "+7 (999) 123-45-67",
  "password": "password123"
}
```

**Особенности:**
- Пароли хешируются перед сохранением
- Автоматическое определение роли по username
- Создание профиля пользователя

### 2. 🎫 Получение JWT токена

```http
POST /user-api/token
Content-Type: application/x-www-form-urlencoded

username=newuser&password=password123
```

**Ответ:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 3. 🔑 Использование токена

```http
GET /api/products/
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## 👥 Ролевая модель

### 🔍 Автоматическое определение ролей

**Администраторы определяются по:**
```python
# 1. Префикс username
is_admin = username.startswith("admin_")

# 2. Флаг в JWT токене
is_admin = payload.get("is_admin", False)
```

### 📋 Матрица прав доступа

| Ресурс | 👤 Обычный пользователь | 👑 Администратор |
|--------|------------------------|------------------|
| **Backend API** |
| Просмотр товаров | Только по категориям | Все товары |
| Создание товаров | ❌ | ✅ |
| Обновление товаров | ❌ | ✅ |
| Удаление товаров | ❌ | ✅ |
| **Cart API** |
| Своя корзина | ✅ | ✅ |
| Все корзины | ❌ | ✅ |
| **Order API** |
| Свои заказы | ✅ | ✅ |
| Все заказы | ❌ | ✅ |
| Изменение статуса | Отмена своих | Любые изменения |
| **User API** |
| Свой профиль | ✅ | ✅ |
| Все профили | ❌ | ✅ |

---

## 🧪 Демо-аккаунты для тестирования

При запуске User Service автоматически создаются тестовые пользователи:

### 👑 Администратор
```json
{
  "username": "swagger_admin",
  "password": "admin123",
  "full_name": "Swagger Admin",
  "phone": "+7 (999) 000-01-01",
  "is_admin": true
}
```

### 👤 Обычный пользователь
```json
{
  "username": "swagger_user", 
  "password": "password123",
  "full_name": "Swagger User",
  "phone": "+7 (999) 000-01-02",
  "is_admin": false
}
```

**📋 Логирование учетных данных:**
```log
2025-07-25 19:00:00 INFO Demo users created successfully:
2025-07-25 19:00:00 INFO Admin: swagger_admin / admin123
2025-07-25 19:00:00 INFO User: swagger_user / password123
```

---

## 🔄 Межсервисное взаимодействие

### 🛡️ Методы аутентификации между сервисами

#### 1. JWT Token (основной метод)
```python
# Cart Service → Order Service
headers = {}
if authorization:
    headers["Authorization"] = authorization

async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{ORDER_SERVICE_URL}/orders/",
        json=order_data,
        headers=headers
    )
```

#### 2. X-User-ID Header (fallback)
```python
# Cart Service → Backend Service
headers = {"X-User-ID": user_id}
if authorization:
    headers["Authorization"] = authorization

response = await client.get(
    f"{BACKEND_SERVICE_URL}/api/products/{product_id}",
    headers=headers
)
```

#### 3. Admin Header (административные операции)
```python
# Order Service → User Service (уведомления)
headers = {"admin": "true"}
response = await client.post(
    f"{USER_SERVICE_URL}/users/notify/order-status",
    json=notification_data,
    headers=headers
)
```

### 🔄 Извлечение пользователя

**Универсальная функция для всех сервисов:**
```python
async def get_user_id(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id")
) -> str:
    """Получение user_id из JWT токена или заголовка"""
    
    # Приоритет: X-User-ID заголовок
    if x_user_id:
        return x_user_id
    
    # Декодирование JWT токена
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload.get("sub")  # username из токена
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    raise HTTPException(status_code=401, detail="Authentication required")
```

---

## 🔒 Механизмы авторизации

### 🛡️ Проверка прав доступа

#### Backend Service (контроль доступа к товарам)
```python
@app.get("/api/products/")
async def get_products(
    category: Optional[str] = None,
    authorization: Optional[str] = Header(None)
):
    # Извлечение пользователя из токена
    user_info = extract_user_from_token(authorization) if authorization else None
    is_admin = user_info.get("is_admin", False) if user_info else False
    
    # Ограничение для обычных пользователей
    if not is_admin and not category:
        raise HTTPException(
            status_code=403, 
            detail="Обычные пользователи должны указать категорию товаров. Используйте параметр 'category'."
        )
    
    # Администраторы могут получить все товары
    return await get_products_from_db(category, is_admin)
```

#### Cart Service (доступ к корзинам)
```python
@app.get("/carts/")
async def get_all_carts(admin: str = Header(None)):
    """Просмотр всех корзин (только для администраторов)"""
    if admin != "true":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return list(user_carts.values())
```

#### Order Service (изменение статусов)
```python
@app.put("/orders/{order_id}/status")
async def update_order_status(
    order_id: str,
    new_status: str,
    admin: str = Header(None)
):
    """Изменение статуса заказа (только администраторы)"""
    if admin != "true":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await update_status(order_id, new_status)
```

---

## 🌐 Swagger UI Integration

### 🚀 Автоматическая аутентификация

**URL:** [http://localhost/swagger/](http://localhost/swagger/)

**Особенности:**
1. **Автоматический вход** под `swagger_admin`
2. **Готовый JWT токен** для тестирования
3. **Переключение ролей** через получение новых токенов
4. **Визуальная индикация** текущего пользователя

### 🔧 Получение токена для Swagger

```http
GET /user-api/swagger-admin-token
```

**Ответ:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "username": "swagger_admin",
  "is_admin": true
}
```

**Использование в Swagger UI:**
1. Скопировать `access_token`
2. Нажать кнопку "Authorize" в Swagger UI
3. Вставить токен в поле "Value"
4. Нажать "Authorize"

---

## ⚠️ Обработка ошибок аутентификации

### 📋 HTTP коды ошибок

| Код | Сценарий | Пример |
|-----|----------|--------|
| `401 Unauthorized` | Отсутствует токен | `{"detail": "Authorization header missing"}` |
| `401 Unauthorized` | Недействительный токен | `{"detail": "Invalid token"}` |
| `401 Unauthorized` | Истекший токен | `{"detail": "Token has expired"}` |
| `403 Forbidden` | Недостаточно прав | `{"detail": "Admin access required"}` |
| `403 Forbidden` | Ограничение доступа | `{"detail": "Обычные пользователи должны указать категорию"}` |

### 🔧 Примеры обработки ошибок

```python
# 401 - Неверный формат токена
{
  "detail": "Invalid authorization header format"
}

# 403 - Недостаточно прав (обычный пользователь пытается создать товар)
{
  "detail": "Admin access required"
}

# 403 - Ограничение доступа к товарам
{
  "detail": "Обычные пользователи должны указать категорию товаров. Используйте параметр 'category'."
}
```

---

## ⚙️ Конфигурация безопасности

### 🔧 Переменные окружения

```yaml
# docker-compose.yml
environment:
  # JWT конфигурация (одинакова для всех сервисов)
  - SECRET_KEY=supersecretkey123    # Секретный ключ для подписи
  - ALGORITHM=HS256                 # Алгоритм подписи
  - ACCESS_TOKEN_EXPIRE_MINUTES=30  # Время жизни токена
```

### 🏗️ Архитектура безопасности

```mermaid
graph TD
    A[Client] -->|1. Register/Login| B[User Service]
    B -->|2. JWT Token| A
    A -->|3. Request + JWT| C[Nginx Proxy]
    C -->|4. Route + JWT| D[Backend/Cart/Order Service]
    D -->|5. Validate JWT| D
    D -->|6. Check Permissions| D
    D -->|7. Response| C
    C -->|8. Response| A
    
    E[Service A] -->|JWT + Headers| F[Service B]
    F -->|Validate + Extract User| F
```

---

## 🧪 Тестирование аутентификации

### 📝 Полный сценарий аутентификации

```bash
#!/bin/bash
# test_auth.sh

BASE_URL="http://localhost"

echo "🔐 Testing authentication system..."

# 1. Регистрация нового пользователя
echo "1. Registering new user..."
curl -X POST "$BASE_URL/user-api/users/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test_user",
    "full_name": "Test User",
    "phone": "+7 (999) 123-45-67",
    "password": "test123"
  }'

# 2. Получение токена
echo -e "\n2. Getting JWT token..."
TOKEN=$(curl -s -X POST "$BASE_URL/user-api/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test_user&password=test123" \
  | jq -r '.access_token')

echo "Token: $TOKEN"

# 3. Тестирование защищенного эндпоинта
echo -e "\n3. Testing protected endpoint..."
curl -X GET "$BASE_URL/api/products/?category=Фрукты" \
  -H "Authorization: Bearer $TOKEN"

# 4. Тестирование административного доступа (должно вернуть 403)
echo -e "\n4. Testing admin endpoint (should fail)..."
curl -X POST "$BASE_URL/api/products/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Product", "category": "Test", "price": 99.99}'

# 5. Получение токена администратора
echo -e "\n5. Getting admin token..."
ADMIN_TOKEN=$(curl -s -X POST "$BASE_URL/user-api/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=swagger_admin&password=admin123" \
  | jq -r '.access_token')

# 6. Тестирование административного доступа (должно сработать)
echo -e "\n6. Testing admin endpoint (should work)..."
curl -X GET "$BASE_URL/api/products/?limit=5" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

echo -e "\n✅ Authentication test completed!"
```

### 🔄 Тестирование межсервисного взаимодействия

```bash
#!/bin/bash
# test_inter_service_auth.sh

BASE_URL="http://localhost"

# Получение токена пользователя
TOKEN=$(curl -s -X POST "$BASE_URL/user-api/token" \
  -d "username=swagger_user&password=password123" \
  | jq -r '.access_token')

# Полный сценарий покупки с передачей токена между сервисами
echo "🛒 Testing full purchase flow with JWT..."

# 1. Добавление товара в корзину (Cart Service)
curl -X POST "$BASE_URL/cart-api/cart/items" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"product_id": "some-product-id", "quantity": 2}'

# 2. Оформление заказа (Cart → Order Service)
curl -X POST "$BASE_URL/cart-api/cart/checkout" \
  -H "Authorization: Bearer $TOKEN"

# 3. Просмотр заказов (Order Service)
curl -X GET "$BASE_URL/order-api/orders/" \
  -H "Authorization: Bearer $TOKEN"

echo "✅ Inter-service authentication test completed!"
```

---

## 🔒 Рекомендации по безопасности

### ✅ Применяемые меры безопасности

1. **🔐 Хеширование паролей**: Все пароли хешируются перед сохранением
2. **⏰ Ограниченное время жизни токенов**: JWT токены истекают через 30 минут
3. **🔑 Секретный ключ**: Единый ключ для всех сервисов (настраивается через ENV)
4. **🛡️ Ролевая модель**: Четкое разделение прав администраторов и пользователей
5. **🔍 Валидация токенов**: Проверка подписи и срока действия на каждом запросе

### 🚀 Рекомендации для продакшена

1. **🔒 HTTPS**: Все взаимодействия должны происходить по HTTPS
2. **🔐 Сложный секретный ключ**: Генерировать криптографически стойкий ключ
3. **⏰ Refresh токены**: Реализовать механизм обновления токенов
4. **📝 Логирование**: Вести журнал аутентификации и авторизации
5. **🛡️ Rate limiting**: Ограничить частоту запросов аутентификации
6. **🔄 Ротация ключей**: Периодическая смена секретных ключей

### 📋 Чек-лист безопасности

- ✅ JWT токены подписываются секретным ключом
- ✅ Пароли хешируются и не хранятся в открытом виде  
- ✅ Ролевая модель разграничивает доступ
- ✅ Токены имеют ограниченное время жизни
- ✅ Все защищенные эндпоинты проверяют токены
- ✅ Межсервисное взаимодействие использует токены
- ✅ Административные операции требуют специальных прав
- ✅ Ошибки аутентификации правильно обрабатываются

---

**🔗 Связанные разделы:**
- **[API Documentation](api_docs.md)** - Примеры использования токенов
- **[Microservices](microservices.md)** - Детали реализации в каждом сервисе  
- **[Testing](testing.md)** - Тестирование системы безопасности
