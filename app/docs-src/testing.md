# Тестирование микросервисов

Для проверки работоспособности и взаимодействия микросервисов в проекте реализован комплексный тестовый скрипт `test_all_microservices.sh`. Этот скрипт последовательно выполняет все основные операции, которые могут быть выполнены пользователем, и проверяет корректность ответов от сервисов.

## Что тестирует скрипт

Скрипт проверяет следующие аспекты системы:

1. **Доступность сервисов** - проверяет, что все микросервисы запущены и отвечают на запросы
2. **Регистрация и аутентификация** - создает тестового пользователя и получает JWT токен
3. **Работа с товарами** - добавляет тестовые товары в базу данных
4. **Работа с корзиной** - добавляет товары в корзину и проверяет их наличие
5. **Оформление заказа** - создает заказ из товаров в корзине
6. **Получение заказов** - проверяет, что созданный заказ появился в списке заказов пользователя
7. **Межсервисное взаимодействие** - проверяет корректную передачу аутентификационных заголовков между сервисами

## Как запустить тест

Для запуска теста выполните следующую команду в корневой директории проекта:

```bash
./test_all_microservices.sh
```

Убедитесь, что все сервисы запущены с помощью Docker Compose:

```bash
cd infra && docker-compose up -d
```

## Структура скрипта

Скрипт состоит из нескольких основных секций:

### 1. Проверка доступности сервисов

```bash
echo "Checking if services are available..."
curl -s http://localhost/api/system/health | grep "ok" || { echo "Backend API is not available"; exit 1; }
curl -s http://localhost/cart-api/health | grep "ok" || { echo "Cart service is not available"; exit 1; }
curl -s http://localhost/order-api/health | grep "ok" || { echo "Order service is not available"; exit 1; }
curl -s http://localhost/user-api/health | grep "ok" || { echo "User service is not available"; exit 1; }
echo "All services are available!"
```

### 2. Регистрация пользователя и получение токена

```bash
echo "Registering a test user..."
TIMESTAMP=$(date +%s)
USERNAME="testuser_${TIMESTAMP}"
PASSWORD="password123"

# Регистрация пользователя
curl -s -X POST http://localhost/user-api/users/register \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${USERNAME}\",\"full_name\":\"Test User\",\"phone\":\"+7 (999) 123-45-67\",\"password\":\"${PASSWORD}\"}"

# Получение токена
TOKEN=$(curl -s -X POST http://localhost/user-api/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${USERNAME}&password=${PASSWORD}" | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "Got token: ${TOKEN}"
```

### 3. Добавление товаров

```bash
echo "Adding products..."
PRODUCT1_ID=$(curl -s -X POST http://localhost/api/products/ \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Test Product 1\",\"category\":\"test\",\"price\":10.99,\"quantity\":100}" | python -c "import sys, json; print(json.load(sys.stdin)['id'])")

PRODUCT2_ID=$(curl -s -X POST http://localhost/api/products/ \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Test Product 2\",\"category\":\"test\",\"price\":20.99,\"quantity\":50}" | python -c "import sys, json; print(json.load(sys.stdin)['id'])")

echo "Added products with IDs: ${PRODUCT1_ID}, ${PRODUCT2_ID}"
```

### 4. Работа с корзиной

```bash
echo "Adding products to cart..."
curl -s -X POST http://localhost/cart-api/cart/items \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d "{\"product_id\":\"${PRODUCT1_ID}\",\"quantity\":2}"

curl -s -X POST http://localhost/cart-api/cart/items \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d "{\"product_id\":\"${PRODUCT2_ID}\",\"quantity\":1}"

echo "Getting cart..."
curl -s http://localhost/cart-api/cart/ \
  -H "Authorization: Bearer ${TOKEN}"
```

### 5. Оформление заказа

```bash
echo "Checking out..."
curl -s -X POST http://localhost/cart-api/cart/checkout \
  -H "Authorization: Bearer ${TOKEN}"
```

### 6. Получение заказов

```bash
echo "Getting orders..."
curl -s http://localhost/user-api/users/me/orders \
  -H "Authorization: Bearer ${TOKEN}"
```

## Обработка ошибок

Скрипт включает обработку ошибок для каждого шага:

1. **Проверка доступности сервисов** - если какой-либо сервис недоступен, скрипт завершается с ошибкой
2. **Получение токена** - если токен не получен, скрипт выводит сообщение об ошибке
3. **Добавление товаров** - если товары не добавлены, скрипт выводит сообщение об ошибке
4. **Работа с корзиной** - скрипт проверяет успешность добавления товаров в корзину
5. **Оформление заказа** - скрипт проверяет успешность создания заказа
6. **Получение заказов** - скрипт проверяет, что заказ появился в списке заказов пользователя

## Интерпретация результатов

После выполнения скрипта вы увидите вывод каждого запроса и его результат. Успешное выполнение всех шагов означает, что все микросервисы работают корректно и взаимодействуют между собой.

Если какой-либо шаг завершается с ошибкой, скрипт выводит соответствующее сообщение, которое поможет определить проблему.

## Расширение и модификация

Скрипт можно расширить для тестирования дополнительных функций:

1. **Отмена заказа** - добавить запрос на отмену созданного заказа
2. **Изменение профиля пользователя** - добавить запрос на обновление информации о пользователе
3. **Удаление товаров из корзины** - добавить запрос на удаление товара из корзины
4. **Проверка статуса заказа** - добавить запрос на проверку изменения статуса заказа с течением времени

## Автоматизация тестирования

Скрипт `test_all_microservices.sh` можно использовать в CI/CD пайплайне для автоматического тестирования системы после каждого изменения кода. Для этого достаточно добавить его вызов после развертывания сервисов в тестовой среде. 