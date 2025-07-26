# Профилирование микросервисов

Система профилирования позволяет анализировать производительность микросервисов с помощью cProfile и визуализировать результаты через snakeviz.

## Архитектура

1. **Переменная окружения ENABLE_PROFILING** - включает/выключает профилирование
2. **Общий Docker volume `profiling_data`** - хранит все файлы профилирования
3. **Snakeviz контейнер** - предоставляет веб-интерфейс для просмотра профилей

## Включение профилирования

Профилирование включается через переменную окружения `ENABLE_PROFILING=true` в docker-compose.yml для следующих сервисов:
- user-service (порт 8003)
- cart-service (порт 8001) 
- order-service (порт 8002)

## Доступные эндпоинты

### Статус профилирования
```
GET /profiling/status
```

### Список профилей
```
GET /profiling/profiles
```

### Статистика профиля
```
GET /profiling/profiles/{filename}/stats
```

### Тестовое профилирование
```
POST /profiling/manual/{operation_name}
```

## Snakeviz - просмотр профилей

Snakeviz доступен по адресу: http://localhost:8080

Интерфейс позволяет:
- Просматривать все сохраненные профили
- Анализировать время выполнения функций
- Изучать call stack в интерактивном режиме

## Примеры использования

### 1. Проверка статуса профилирования
```bash
curl http://localhost/users/profiling/status
curl http://localhost/cart/profiling/status
curl http://localhost/orders/profiling/status
```

### 2. Запуск тестового профилирования
```bash
# User service
curl -X POST http://localhost/users/profiling/manual/test_load

# Cart service  
curl -X POST http://localhost/cart/profiling/manual/test_load

# Order service
curl -X POST http://localhost/orders/profiling/manual/test_load
```

### 3. Получение списка профилей
```bash
curl http://localhost/users/profiling/profiles
```

### 4. Просмотр статистики профиля
```bash
curl http://localhost/users/profiling/profiles/user-service_endpoint_manual_operation_20231201_143022.prof/stats
```

## Профилируемые эндпоинты

### User Service
- Регистрация пользователя (`/users/register`)
- Аутентификация (`/token`) 
- Получение профиля (`/users/me/profile`)

### Cart Service
- Добавление товара в корзину (`/cart/items`)

### Order Service
- (Добавить после интеграции)

## Файлы профилирования

Профили сохраняются в формате:
```
{service-name}_{operation}_{timestamp}.prof
```

Примеры:
- `user-service_endpoint_user_registration_20231201_143022.prof`
- `cart-service_endpoint_add_to_cart_20231201_143055.prof`
- `order-service_manual_test_load_20231201_143122.prof`

## Мониторинг производительности

1. **Автоматическое профилирование** - ключевые эндпоинты автоматически профилируются при включенном режиме
2. **Ручное профилирование** - используйте тестовые эндпоинты для целенаправленного анализа
3. **Визуализация** - используйте Snakeviz для детального анализа узких мест

## Лучшие практики

1. Включайте профилирование только при необходимости (влияет на производительность)
2. Регулярно очищайте старые профили
3. Используйте описательные имена операций для ручного профилирования
4. Анализируйте профили после значительных изменений в коде
5. Сравнивайте профили до и после оптимизаций

## Отключение профилирования

Установите `ENABLE_PROFILING=false` или уберите переменную из docker-compose.yml и перезапустите контейнеры:

```bash
docker-compose down
docker-compose up -d
```
