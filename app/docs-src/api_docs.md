# Обзор API

Наш API следует принципам REST. Все эндпоинты доступны через соответствующие префиксы.

## Основные ресурсы

*   **/api**: Основной API для работы с товарами.
*   **/cart-api**: API сервиса корзины.
*   **/order-api**: API сервиса заказов.
*   **/user-api**: API сервиса пользователей.

## Аутентификация и заголовки

Для аутентификации используется JWT токен, который передается в заголовке `Authorization`. Формат заголовка:
```
Authorization: Bearer <jwt_token>
```

Для идентификации пользователя между сервисами также может использоваться заголовок `X-User-ID`, который содержит имя пользователя:
```
X-User-ID: username
```

Сервисы поддерживают оба варианта аутентификации, что обеспечивает гибкость при межсервисном взаимодействии.

## Реализованные эндпоинты

### Система (/api/system)

* **GET /api/system/health** - Проверка состояния сервиса и подключения к БД

### Товары (/api/products)

* **GET /api/products/** - Получение списка всех товаров
* **POST /api/products/** - Создание нового товара
* **GET /api/products/{product_id}** - Получение информации о конкретном товаре
* **PUT /api/products/{product_id}** - Обновление информации о товаре
* **DELETE /api/products/{product_id}** - Удаление товара

### Корзина (/cart-api)

* **GET /cart-api/cart/** - Получение текущей корзины пользователя
* **POST /cart-api/cart/items** - Добавление товара в корзину
* **PUT /cart-api/cart/items/{item_id}** - Изменение количества товара в корзине
* **DELETE /cart-api/cart/items/{item_id}** - Удаление товара из корзины
* **GET /cart-api/cart/total** - Получение общей стоимости корзины
* **POST /cart-api/cart/checkout** - Оформление заказа из корзины (передает JWT токен в сервис заказов)
* **DELETE /cart-api/cart/** - Очистка корзины
* **GET /cart-api/carts/** - Получение всех корзин (только для администраторов)

### Заказы (/order-api)

* **GET /order-api/orders/** - Получение списка заказов пользователя или всех заказов для админа
* **POST /order-api/orders/** - Создание нового заказа (поддерживает аутентификацию через JWT и X-User-ID)
* **GET /order-api/orders/{order_id}** - Получение информации о конкретном заказе
* **PUT /order-api/orders/{order_id}/status** - Обновление статуса заказа (только для администраторов)
* **PUT /order-api/orders/{order_id}/cancel** - Отмена заказа
* **GET /order-api/orders/statuses/list** - Получение списка возможных статусов заказа

### Пользователи (/user-api)

* **POST /user-api/users/register** - Регистрация нового пользователя
* **POST /user-api/token** - Аутентификация пользователя и получение токена
* **GET /user-api/users/me** - Получение информации о текущем пользователе
* **GET /user-api/users/me/profile** - Получение профиля пользователя с информацией о заказах и корзине
* **PUT /user-api/users/me** - Обновление информации о пользователе
* **GET /user-api/users/me/orders** - Получение списка заказов пользователя (передает JWT токен и X-User-ID в сервис заказов)
* **GET /user-api/users/me/cart** - Получение корзины пользователя (передает JWT токен в сервис корзины)
* **POST /user-api/users/me/orders** - Оформление заказа из корзины пользователя
* **GET /user-api/users/me/total-spent** - Получение общей суммы потраченных средств

## Примеры использования API

### Регистрация пользователя

```bash
curl -X POST http://localhost/user-api/users/register \
  -H "Content-Type: application/json" \
  -d '{"username": "newuser", "full_name": "New User", "phone": "+7 (999) 123-45-67", "password": "password123"}'
```

### Аутентификация и получение токена

```bash
curl -X POST http://localhost/user-api/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=password123"
```

### Получение профиля пользователя

```bash
curl http://localhost/user-api/users/me/profile \
  -H "Authorization: Bearer {token}"
```

### Добавление товара в корзину

```bash
curl -X POST http://localhost/cart-api/cart/items \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{"product_id": "f767c2cb-215d-469e-a3be-c6e40a6cf47f", "quantity": 2}'
```

### Оформление заказа из корзины

```bash
curl -X POST http://localhost/user-api/users/me/orders \
  -H "Authorization: Bearer {token}"
```

### Получение списка заказов пользователя

```bash
curl http://localhost/user-api/users/me/orders \
  -H "Authorization: Bearer {token}"
```

### Отмена заказа

```bash
curl -X PUT http://localhost/order-api/orders/{order_id}/cancel \
  -H "Authorization: Bearer {token}"
```

## Интерактивный справочник

Для детального изучения каждого эндпоинта, его параметров и ответов, пожалуйста, используйте интерактивный справочник Swagger UI.

**[>> Открыть Swagger UI <<](/api/swagger)**

### Продвинутый вариант: Встроенный Swagger

Для максимального удобства, Swagger UI можно встроить прямо на эту страницу с помощью `<iframe>`:

<iframe src="/api/swagger" style="width:100%; height:800px; border:1px solid #ccc;"></iframe>

