# 🔧 API Documentation - Product Store

Полная документация по REST API всех микросервисов системы Product Store с примерами использования, аутентификацией и интерактивным тестированием.

## 🌐 Обзор API

Система построена на микросервисной архитектуре с 4 основными API сервисами, доступными через единую точку входа Nginx:

| Сервис | Базовый URL | Описание |
|--------|-------------|----------|
| **Backend API** | `/api/*` | Управление товарами и каталогом |
| **Cart API** | `/cart-api/*` | Управление корзиной покупок |
| **Order API** | `/order-api/*` | Обработка и отслеживание заказов |
| **User API** | `/user-api/*` | Аутентификация и управление пользователями |

**Базовый URL для всех запросов:** `http://localhost/`

## 📋 Интерактивная документация

### 🚀 Swagger UI - Объединенный интерфейс

**URL:** [http://localhost/swagger/](http://localhost/swagger/)

**Возможности:**
- ✅ **Единый интерфейс** для всех микросервисов
- ✅ **Интерактивное тестирование** прямо в браузере
- ✅ **Автоматическая аутентификация** с правами администратора
- ✅ **Поддержка JWT токенов** для защищенных эндпоинтов
- ✅ **Переключение ролей** (admin/user) для тестирования доступа

### 🔐 Демо-аккаунты для тестирования

При запуске системы автоматически создаются тестовые пользователи:

| Пользователь | Пароль | Роль | Описание |
|--------------|--------|------|----------|
| `swagger_admin` | `admin123` | 👑 Администратор | Полный доступ ко всем функциям |
| `swagger_user` | `password123` | 👤 Пользователь | Ограниченный доступ |

**Автоматический вход:** Swagger UI автоматически авторизуется под `swagger_admin`

---

## 🏪 Backend API (`/api/*`)

**Управление товарами и каталогом магазина**

### 📦 Products API

#### Просмотр товаров

```http
GET /api/products/                    # Список товаров (с контролем доступа)
GET /api/products/{product_id}        # Детали конкретного товара
GET /api/products/categories/list     # Список всех категорий
GET /api/products/by-category/{cat}   # Товары конкретной категории
```

**Контроль доступа к товарам:**
- 👤 **Обычные пользователи**: должны указать `category` параметр
- 👑 **Администраторы**: могут получить все товары без ограничений
- 🌐 **Без авторизации**: только с указанием категории

**Пример запроса:**
```bash
# Для обычных пользователей (обязательна категория)
GET /api/products/?category=Фрукты&limit=10&skip=0
Authorization: Bearer JWT_TOKEN

# Для администраторов (категория опциональна)
GET /api/products/?limit=20&sort_by=price&sort_order=desc
Authorization: Bearer JWT_TOKEN
```

**Параметры фильтрации и пагинации:**
- `category` - категория товаров (обязательна для non-admin)
- `skip` - количество товаров для пропуска (offset)
- `limit` - максимальное количество товаров (1-100)
- `sort_by` - поле сортировки (`name` или `price`)
- `sort_order` - порядок сортировки (`asc` или `desc`)
- `min_price` - минимальная цена
- `max_price` - максимальная цена

#### Управление товарами (только администраторы)

```http
POST   /api/products/                 # Создание товара
PUT    /api/products/{product_id}     # Обновление товара
DELETE /api/products/{product_id}     # Удаление товара
```

**Пример создания товара:**
```json
POST /api/products/
Authorization: Bearer ADMIN_JWT_TOKEN
Content-Type: application/json

{
  "name": "Яблоки Гала",
  "category": "Фрукты",
  "price": 89.99,
  "stock_count": 150,
  "description": "Сладкие яблоки сорта Гала",
  "manufacturer": "Сады России"
}
```

### 🔧 System API

```http
GET /system/health                    # Health check + статус БД
GET /                                 # Информация о сервисе
GET /metrics                          # Prometheus метрики
```

---

## 🛒 Cart API (`/cart-api/*`)

**Управление корзиной покупок с валидацией остатков**

### 🛍️ Основные операции с корзиной

```http
GET    /cart/                         # Просмотр корзины
POST   /cart/items                    # Добавление товара
PUT    /cart/items/{item_id}          # Обновление количества
DELETE /cart/items/{item_id}          # Удаление товара
DELETE /cart/                         # Очистка корзины
POST   /cart/checkout                 # Оформление заказа
```

**Пример добавления товара в корзину:**
```json
POST /cart-api/cart/items
Authorization: Bearer JWT_TOKEN
Content-Type: application/json

{
  "product_id": "f767c2cb-215d-469e-a3be-c6e40a6cf47f",
  "quantity": 2
}
```

**Пример ответа:**
```json
{
  "id": "item-uuid",
  "product_id": "f767c2cb-215d-469e-a3be-c6e40a6cf47f",
  "name": "Яблоки Гала",
  "price": 89.99,
  "quantity": 2,
  "total_price": 179.98
}
```

### 📋 Дополнительные функции

```http
POST /products/{product_id}/view      # Запись просмотра товара
GET  /products/recent-views           # Недавно просмотренные товары
GET  /carts/                          # Все корзины (admin only)
```

### 🔄 Особенности реализации

**Поиск товаров в корзине:**
- Сначала поиск по `item_id` (UUID элемента корзины)
- Если не найден, поиск по `product_id` (UUID товара)
- Поддержка удаления всех экземпляров товара по `product_id`

**Валидация остатков:**
- Проверка наличия товара при добавлении
- Проверка остатков при изменении количества
- Интеграция с Backend API для получения актуальной информации

---

## 📦 Order API (`/order-api/*`)

**Обработка заказов с автоматическим изменением статусов**

### 📋 Управление заказами

```http
GET    /orders/                       # Список заказов пользователя
POST   /orders/                       # Создание заказа (из Cart API)
GET    /orders/{order_id}             # Детали заказа
PUT    /orders/{order_id}/cancel      # Отмена заказа
GET    /orders/statuses/list          # Список всех статусов
```

### 👑 Административные функции

```http
PUT /orders/{order_id}/status         # Изменение статуса заказа (admin only)
```

**Доступные статусы заказов:**
- `CREATED` - Создан
- `PROCESSING` - Обрабатывается  
- `SHIPPING` - Доставляется
- `DELIVERED` - Доставлен
- `CANCELLED` - Отменен

### 🔄 Автоматическая обработка заказов

**Жизненный цикл заказа:**
```
CREATED → PROCESSING (5 сек) → SHIPPING (5 сек) → DELIVERED (60-300 сек)
```

**Ограничения отмены:**
- `CREATED`, `PROCESSING` - может отменить пользователь или админ
- `SHIPPING` - может отменить только админ
- `DELIVERED`, `CANCELLED` - отмена невозможна

**Пример создания заказа:**
```json
POST /order-api/orders/
Authorization: Bearer JWT_TOKEN
Content-Type: application/json

{
  "items": [
    {
      "product_id": "product-uuid",
      "name": "Яблоки Гала",
      "price": 89.99,
      "quantity": 2
    }
  ],
  "total": 179.98
}
```

---

## 👤 User API (`/user-api/*`)

**Аутентификация и управление пользователями**

### 🔐 Аутентификация

```http
POST /users/register                  # Регистрация пользователя
POST /token                           # Получение JWT токена
GET  /users/me                        # Профиль пользователя
PUT  /users/me                        # Обновление профиля
```

**Пример регистрации:**
```json
POST /user-api/users/register
Content-Type: application/json

{
  "username": "newuser",
  "full_name": "New User",
  "phone": "+7 (999) 123-45-67",
  "password": "password123"
}
```

**Пример получения токена:**
```http
POST /user-api/token
Content-Type: application/x-www-form-urlencoded

username=newuser&password=password123
```

**Ответ с токеном:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 👤 Профиль пользователя

```http
GET  /users/me/profile                # Полный профиль с агрегацией данных
GET  /users/me/orders                 # История заказов
GET  /users/me/cart                   # Текущая корзина
POST /users/me/orders                 # Оформление заказа из корзины
GET  /users/me/total-spent            # Общая сумма покупок
```

**Пример полного профиля:**
```json
GET /user-api/users/me/profile
Authorization: Bearer JWT_TOKEN

{
  "username": "newuser",
  "full_name": "New User",
  "phone": "+7 (999) 123-45-67",
  "id": "00000001",
  "created_at": "2025-07-25T19:00:00",
  "total_spent": 359.96,
  "is_admin": false,
  "current_cart_total": 179.98,
  "orders": [
    {
      "id": "order-uuid",
      "status": "DELIVERED",
      "total": 179.98,
      "created_at": "2025-07-25T18:00:00"
    }
  ]
}
```

### 🔧 Системные эндпоинты

```http
GET  /                                # Информация о сервисе
GET  /health                          # Health check
POST /users/notify/order-status       # Уведомления от Order Service
GET  /swagger-admin-token             # Токен админа для Swagger UI
```

---

## 🔐 Система аутентификации

### 🎫 JWT Токены

**Конфигурация:**
- **Алгоритм**: HS256
- **Время жизни**: 30 минут (по умолчанию)
- **Секретный ключ**: `supersecretkey123` (настраивается через ENV)

**Payload токена:**
```json
{
  "sub": "username",           # Имя пользователя
  "is_admin": true,           # Флаг администратора
  "exp": 1690311600           # Время истечения (Unix timestamp)
}
```

### 🛡️ Методы аутентификации

#### 1. Authorization Header (основной метод)
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### 2. X-User-ID Header (для внутренних вызовов)
```http
X-User-ID: username
```

#### 3. Admin Header (для административных операций)
```http
admin: true
```

### 👑 Ролевая модель

**Автоматическое определение роли:**
- **Администраторы**: username начинается с `admin_` или флаг `is_admin: true`
- **Обычные пользователи**: все остальные

**Права доступа:**

| Операция | Обычный пользователь | Администратор |
|----------|---------------------|---------------|
| Просмотр товаров | Только по категориям | Все товары |
| Управление товарами | ❌ | ✅ |
| Своя корзина | ✅ | ✅ |
| Все корзины | ❌ | ✅ |
| Свои заказы | ✅ | ✅ |
| Все заказы | ❌ | ✅ |
| Изменение статуса заказа | ❌ | ✅ |

---

## 🔄 Сценарии использования

### 🛒 Полный сценарий покупки

```bash
# 1. Регистрация пользователя
curl -X POST http://localhost/user-api/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "customer1",
    "full_name": "Customer One", 
    "phone": "+7 (999) 123-45-67",
    "password": "password123"
  }'

# 2. Получение JWT токена
TOKEN=$(curl -X POST http://localhost/user-api/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=customer1&password=password123" \
  | jq -r '.access_token')

# 3. Просмотр товаров по категории (обязательно для обычных пользователей)
curl -X GET "http://localhost/api/products/?category=Фрукты&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# 4. Добавление товара в корзину
curl -X POST http://localhost/cart-api/cart/items \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "product_id": "PRODUCT_UUID",
    "quantity": 2
  }'

# 5. Просмотр корзины
curl -X GET http://localhost/cart-api/cart/ \
  -H "Authorization: Bearer $TOKEN"

# 6. Оформление заказа
curl -X POST http://localhost/user-api/users/me/orders \
  -H "Authorization: Bearer $TOKEN"

# 7. Проверка статуса заказа
curl -X GET http://localhost/user-api/users/me/orders \
  -H "Authorization: Bearer $TOKEN"
```

### 👑 Административные операции

```bash
# Получение токена администратора
ADMIN_TOKEN=$(curl -X POST http://localhost/user-api/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=swagger_admin&password=admin123" \
  | jq -r '.access_token')

# Просмотр всех товаров (без ограничений по категории)
curl -X GET "http://localhost/api/products/?limit=20&sort_by=price" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Создание нового товара
curl -X POST http://localhost/api/products/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "name": "Новый товар",
    "category": "Категория",
    "price": 99.99,
    "stock_count": 100,
    "description": "Описание товара"
  }'

# Просмотр всех корзин
curl -X GET http://localhost/cart-api/carts/ \
  -H "admin: true"

# Принудительное изменение статуса заказа
curl -X PUT http://localhost/order-api/orders/ORDER_ID/status \
  -H "admin: true" \
  -H "Content-Type: application/json" \
  -d '"DELIVERED"'
```

---

## 📊 Коды ответов HTTP

### ✅ Успешные ответы

| Код | Описание | Примеры использования |
|-----|----------|----------------------|
| `200 OK` | Успешный запрос | GET запросы, обновления |
| `201 Created` | Ресурс создан | POST создание товара, пользователя |
| `204 No Content` | Успешно, без содержимого | DELETE операции |

### ⚠️ Ошибки клиента (4xx)

| Код | Описание | Примеры |
|-----|----------|---------|
| `400 Bad Request` | Неверные данные запроса | Неверный JSON, валидация |
| `401 Unauthorized` | Требуется аутентификация | Отсутствует JWT токен |
| `403 Forbidden` | Недостаточно прав | Обычный пользователь пытается создать товар |
| `404 Not Found` | Ресурс не найден | Несуществующий товар или заказ |

### ❌ Ошибки сервера (5xx)

| Код | Описание | Примеры |
|-----|----------|---------|
| `500 Internal Server Error` | Внутренняя ошибка | Ошибка в коде сервиса |
| `503 Service Unavailable` | Сервис недоступен | БД недоступна, сервис перегружен |

### 📝 Формат ошибок

```json
{
  "detail": "Описание ошибки",
  "error_code": "OPTIONAL_ERROR_CODE",
  "timestamp": "2025-07-25T19:00:00Z"
}
```

**Примеры ошибок:**
```json
// 403 Forbidden - недостаточно прав
{
  "detail": "Обычные пользователи должны указать категорию товаров. Используйте параметр 'category'."
}

// 400 Bad Request - недостаточно товара на складе
{
  "detail": "Not enough items in stock"
}

// 404 Not Found - товар не найден
{
  "detail": "Product with id f767c2cb-215d-469e-a3be-c6e40a6cf47f not found"
}
```

---

## 🔧 Интеграция и тестирование

### 📋 Postman Collection

Для удобства тестирования рекомендуется создать Postman коллекцию с основными запросами:

1. **Environment Variables:**
   ```
   baseUrl: http://localhost
   userToken: {{получается из login запроса}}
   adminToken: {{получается из admin login запроса}}
   ```

2. **Pre-request Scripts для автоматической аутентификации:**
   ```javascript
   // Автоматическое получение токена пользователя
   pm.sendRequest({
     url: pm.environment.get("baseUrl") + "/user-api/token",
     method: 'POST',
     header: {'Content-Type': 'application/x-www-form-urlencoded'},
     body: {
       mode: 'urlencoded',
       urlencoded: [
         {key: 'username', value: 'swagger_user'},
         {key: 'password', value: 'password123'}
       ]
     }
   }, function(err, res) {
     if (res.json().access_token) {
       pm.environment.set("userToken", res.json().access_token);
     }
   });
   ```

### 🧪 Автоматизированное тестирование

**Bash скрипт для smoke testing:**
```bash
#!/bin/bash
# test_api.sh

BASE_URL="http://localhost"

# Health checks
curl -f "$BASE_URL/api/system/health" || exit 1
curl -f "$BASE_URL/cart-api/health" || exit 1  
curl -f "$BASE_URL/order-api/health" || exit 1
curl -f "$BASE_URL/user-api/health" || exit 1

echo "✅ All services are healthy"

# User registration and authentication
TOKEN=$(curl -s -X POST "$BASE_URL/user-api/users/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"test_user","full_name":"Test User","phone":"+7999","password":"test123"}' \
  && curl -s -X POST "$BASE_URL/user-api/token" \
  -d "username=test_user&password=test123" | jq -r '.access_token')

echo "✅ User registered and authenticated"

# Test protected endpoints
curl -f -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/products/?category=Фрукты" || exit 1
curl -f -H "Authorization: Bearer $TOKEN" "$BASE_URL/cart-api/cart/" || exit 1

echo "✅ Protected endpoints accessible"
echo "🎉 All tests passed!"
```

---

**📚 Дополнительные ресурсы:**
- **[Swagger UI](http://localhost/swagger/)** - интерактивное тестирование
- **[Grafana](http://localhost:3000)** - мониторинг API производительности  
- **[Prometheus](http://localhost:9090)** - метрики API запросов
