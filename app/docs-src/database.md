# База данных

В проекте используется распределенная NoSQL база данных Cassandra для хранения информации о товарах.

## Общая информация

- **Тип базы данных**: Apache Cassandra 4.1
- **Keyspace**: store
- **Режим репликации**: SimpleStrategy с replication_factor=1 (для разработки)

## Схема данных

### Таблица: products

Таблица `products` хранит информацию о товарах, доступных в магазине.

#### Структура таблицы

| Колонка    | Тип      | Описание                           |
|------------|----------|-----------------------------------|
| id         | UUID     | Первичный ключ, идентификатор товара |
| name       | TEXT     | Название товара                    |
| category   | TEXT     | Категория товара                   |
| price      | DECIMAL  | Цена товара                        |
| quantity   | INT      | Количество товара на складе         |

#### Индексы

- Первичный ключ: `id`

#### Запросы

##### Чтение данных

1. **Получение всех товаров**
   ```cql
   SELECT id, name, category, price, quantity FROM products;
   ```
   - Используется в: `app/backend/src/api/products.py` - функция `list_products()`

2. **Получение товара по ID**
   ```cql
   SELECT id, name, category, price, quantity FROM products WHERE id = ?;
   ```
   - Используется в: `app/backend/src/api/products.py` - функция `get_product()`

##### Запись данных

1. **Создание нового товара**
   ```cql
   INSERT INTO products (id, name, category, price, quantity) VALUES (?, ?, ?, ?, ?);
   ```
   - Используется в: `app/backend/src/api/products.py` - функция `create_product()`

2. **Обновление товара**
   ```cql
   UPDATE products SET name = ?, category = ?, price = ?, quantity = ? WHERE id = ?;
   ```
   - Используется в: `app/backend/src/api/products.py` - функция `update_product()`

3. **Удаление товара**
   ```cql
   DELETE FROM products WHERE id = ?;
   ```
   - Используется в: `app/backend/src/api/products.py` - функция `delete_product()`

## Взаимодействие с базой данных

### Инициализация и подключение

Подключение к базе данных происходит при запуске приложения в файле `app/backend/src/services/cassandra.py`:

```python
def get_cassandra_session():
    """Подключение к Cassandra и возвращение сессии."""
    cassandra_host = os.environ.get("CASSANDRA_HOST", "127.0.0.1")
    cluster = Cluster([cassandra_host])
    session = cluster.connect()

    rows = session.execute("SELECT keyspace_name FROM system_schema.keyspaces")
    if KEYSPACE in [row[0] for row in rows]:
        log.info(f"Keyspace '{KEYSPACE}' already exists.")
    else:
        log.info(f"Creating keyspace '{KEYSPACE}'...")
        session.execute(f"""
            CREATE KEYSPACE {KEYSPACE}
            WITH replication = {{ 'class': 'SimpleStrategy', 'replication_factor': '1' }}
        """)

    session.set_keyspace(KEYSPACE)
    return session
```

### Создание схемы

Создание таблиц происходит при запуске приложения в файле `app/backend/src/services/cassandra.py`:

```python
def create_schema(session):
    """Создание таблиц в Cassandra."""
    log.info("Creating table 'products'...")
    session.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id UUID PRIMARY KEY,
            name TEXT,
            category TEXT,
            price DECIMAL,
            quantity INT
        );
    """)
    log.info("Table 'products' created.")
```

### Взаимодействие микросервисов с базой данных

1. **Backend Service** - прямое взаимодействие с базой данных Cassandra:
   - Создание и обновление схемы
   - CRUD-операции для товаров

2. **Cart Service** - косвенное взаимодействие через Backend API:
   - Проверка наличия товаров
   - Получение информации о товарах

3. **Order Service** - косвенное взаимодействие через Backend API:
   - Получение информации о товарах

4. **User Service** - косвенное взаимодействие через Cart Service и Order Service:
   - Получение информации о корзине пользователя
   - Получение информации о заказах пользователя

## Диаграмма доступа к данным

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ User Service│     │ Cart Service│     │Order Service│
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │Backend API  │
                    └──────┬──────┘
                           │
                           │
                           ▼
                    ┌─────────────┐
                    │  Cassandra  │
                    └─────────────┘
```

## Оптимизация и масштабирование

В текущей реализации используется базовая конфигурация Cassandra для разработки. Для продакшн-окружения рекомендуется:

1. **Настроить кластер Cassandra** с несколькими узлами для обеспечения высокой доступности и отказоустойчивости.
2. **Увеличить replication_factor** до 3 или более для обеспечения надежности данных.
3. **Использовать NetworkTopologyStrategy** вместо SimpleStrategy для распределения данных по нескольким дата-центрам.
4. **Настроить индексы** для оптимизации запросов по категориям и другим полям.
5. **Реализовать кэширование** часто запрашиваемых данных для уменьшения нагрузки на базу данных.

## Мониторинг и обслуживание

Для мониторинга состояния базы данных используется эндпоинт `/api/system/health`, который проверяет доступность Cassandra и возможность выполнения запросов.

Для обслуживания базы данных рекомендуется:

1. **Регулярное резервное копирование** данных.
2. **Мониторинг производительности** запросов и использования ресурсов.
3. **Очистка устаревших данных** для оптимизации использования дискового пространства.
4. **Обновление версии Cassandra** для получения исправлений безопасности и новых функций. 