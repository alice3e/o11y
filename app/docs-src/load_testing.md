# ⚡ Нагрузочное тестирование

Система нагрузочного тестирования Product Store на базе Locust для комплексной проверки производительности всех микросервисов под реальной нагрузкой.

## 🎯 Цели нагрузочного тестирования

### ✅ Основные задачи
- **📊 Оценка производительности** всех микросервисов
- **🔍 Поиск узких мест** в архитектуре системы
- **🚨 Тестирование отказоустойчивости** при высокой нагрузке
- **📈 Определение максимальной пропускной способности**
- **⚠️ Проверка системы мониторинга** и алертов
- **🔧 Валидация горизонтального масштабирования**

### 🎪 Типы тестирования
- **🟢 Smoke Testing**: Базовая работоспособность (20 пользователей)
- **📊 Load Testing**: Ожидаемая нагрузка (100 пользователей)
- **🔥 Stress Testing**: Пиковая нагрузка (300+ пользователей)
- **💣 Spike Testing**: Резкие всплески нагрузки
- **⏱️ Endurance Testing**: Длительная стабильная нагрузка

---

## 🏗️ Архитектура тестирования

### 🐳 Docker-интеграция

```yaml
# infra/docker-compose.yml
locust:
  image: locustio/locust:latest
  ports:
    - "8089:8089"  # Web UI
  volumes:
    - ./locust:/mnt/locust
  command: >
    locust
    --host=http://nginx
    --web-host=0.0.0.0
    --web-port=8089
    --locustfile=/mnt/locust/locustfile.py
  depends_on:
    - nginx
    - backend
    - cart-service
    - order-service
    - user-service
  networks:
    - backend
```

### 🌐 Доступ к тестированию

| Интерфейс | URL | Описание |
|-----------|-----|----------|
| **🎯 Locust Web UI** | [http://localhost:8089](http://localhost:8089) | Управление тестами |
| **📊 Grafana Dashboard** | [http://localhost:3000](http://localhost:3000) | Мониторинг производительности |
| **📈 Prometheus Metrics** | [http://localhost:9090](http://localhost:9090) | Метрики в реальном времени |

---

## 👥 Профили пользователей

### 🛒 RegularUser (60% нагрузки)

**Полный покупательский путь с реалистичными паузами**

```python
class RegularUser(HttpUser):
    weight = 60  # 60% от общего количества пользователей
    wait_time = between(2, 8)  # Реалистичные паузы между действиями
    
    def on_start(self):
        """Регистрация нового пользователя"""
        self.username = f"user_{random.randint(10000, 99999)}"
        self.register_and_login()
    
    @task(3)
    def browse_products(self):
        """Просмотр товаров по категориям (высокая частота)"""
        categories = ["Фрукты", "Овощи", "Молочные", "Мясо", "Рыба"]
        category = random.choice(categories)
        self.client.get(f"/api/products/?category={category}&limit=20", 
                       headers=self.headers)
    
    @task(2)
    def view_product_details(self):
        """Детальный просмотр товара"""
        self.client.get(f"/api/products/{self.get_random_product_id()}", 
                       headers=self.headers)
    
    @task(1)
    def manage_cart(self):
        """Управление корзиной"""
        # Добавление товара
        self.client.post("/cart-api/cart/items", 
                        json={"product_id": self.get_random_product_id(), "quantity": random.randint(1, 3)},
                        headers=self.headers)
        
        # Просмотр корзины
        self.client.get("/cart-api/cart/", headers=self.headers)
    
    @task(1)
    def view_profile(self):
        """Просмотр профиля с агрегацией данных"""
        self.client.get("/user-api/users/me/profile", headers=self.headers)
```

### 👑 AdminUser (15% нагрузки)

**Административные операции и управление каталогом**

```python
class AdminUser(HttpUser):
    weight = 15  # 15% администраторов
    wait_time = between(5, 15)  # Админы работают медленнее
    
    def on_start(self):
        """Аутентификация как администратор"""
        response = self.client.post("/user-api/token", data={
            "username": "swagger_admin",
            "password": "admin123"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(2)
    def manage_products(self):
        """Управление товарами"""
        # Создание товара
        product_data = self.generate_realistic_product()
        self.client.post("/api/products/", 
                        json=product_data, 
                        headers=self.headers)
        
        # Просмотр всех товаров (без ограничения по категории)
        self.client.get("/api/products/?limit=50&sort_by=price", 
                       headers=self.headers)
    
    @task(1)
    def monitor_system(self):
        """Мониторинг системы"""
        # Просмотр всех корзин
        self.client.get("/cart-api/carts/", headers={"admin": "true"})
        
        # Health check
        self.client.get("/api/system/health")
```

### 🌐 AnonymousUser (20% нагрузки)

**Просмотр без регистрации (реальный поведенческий паттерн)**

```python
class AnonymousUser(HttpUser):
    weight = 20  # 20% анонимных пользователей
    wait_time = between(1, 5)  # Быстрый просмотр
    
    @task(4)
    def browse_categories(self):
        """Просмотр товаров по категориям"""
        categories = ["Фрукты", "Овощи", "Молочные"]
        category = random.choice(categories)
        self.client.get(f"/api/products/?category={category}&limit=20")
    
    @task(2)
    def view_product_details(self):
        """Просмотр деталей товара без авторизации"""
        # Получаем список товаров
        response = self.client.get("/api/products/?category=Фрукты&limit=10")
        if response.status_code == 200:
            products = response.json().get("products", [])
            if products:
                product = random.choice(products)
                self.client.get(f"/api/products/{product['id']}")
    
    @task(1)
    def check_system_health(self):
        """Проверка доступности системы"""
        self.client.get("/api/system/health")
```

### 💥 StressUser (5% нагрузки)

**Интенсивная нагрузка для стресс-тестирования**

```python
class StressUser(HttpUser):
    weight = 5  # 5% интенсивных пользователей
    wait_time = between(0.1, 1)  # Минимальные паузы
    
    @task(5)
    def rapid_api_calls(self):
        """Быстрые запросы к API"""
        endpoints = [
            "/api/products/?category=Фрукты&limit=5",
            "/cart-api/health",
            "/order-api/health", 
            "/user-api/health"
        ]
        endpoint = random.choice(endpoints)
        self.client.get(endpoint)
    
    @task(2)
    def intensive_cart_operations(self):
        """Интенсивные операции с корзиной"""
        if hasattr(self, 'headers'):
            # Быстрое добавление/удаление товаров
            self.client.post("/cart-api/cart/items", 
                           json={"product_id": f"stress-product-{random.randint(1, 100)}", "quantity": 1},
                           headers=self.headers)
```

---

## 🚀 Запуск тестирования

### 🎛️ Быстрые команды

```bash
# Переход в директорию инфраструктуры
cd infra

# Запуск всех сервисов
docker-compose up -d

# Запуск Locust через Docker
docker-compose up locust

# Альтернативно: запуск локально
pip install locust
locust --host=http://localhost --locustfile=locust/locustfile.py
```

### 🎯 Предустановленные сценарии

#### 🟢 Smoke Test (Проверка работоспособности)
```bash
# Веб-интерфейс: http://localhost:8089
# Настройки:
# - Users: 20
# - Spawn rate: 5 users/sec
# - Duration: 5 minutes
# - Цель: Убедиться что все эндпоинты отвечают
```

#### 📊 Load Test (Обычная нагрузка)
```bash
# Настройки:
# - Users: 100
# - Spawn rate: 10 users/sec  
# - Duration: 15 minutes
# - Цель: Тестирование при ожидаемой нагрузке
```

#### 🔥 Stress Test (Предельная нагрузка)
```bash
# Настройки:
# - Users: 300
# - Spawn rate: 20 users/sec
# - Duration: 10 minutes
# - Цель: Найти точку отказа системы
```

#### 💣 Spike Test (Резкий всплеск)
```bash
# Настройки:
# - Users: 500
# - Spawn rate: 50 users/sec
# - Duration: 5 minutes
# - Цель: Тестирование реакции на пиковые нагрузки
```

---

## 📊 Метрики и мониторинг

### 🎯 Ключевые показатели производительности

#### ⚡ Response Time метрики
| Метрика | Целевое значение | Критическое значение |
|---------|------------------|---------------------|
| **P50 (медиана)** | < 100ms | > 300ms |
| **P95** | < 200ms | > 500ms |
| **P99** | < 500ms | > 1000ms |
| **P99.9** | < 1000ms | > 2000ms |

#### 📈 Throughput метрики
| Сервис | Целевой RPS | Максимальный RPS |
|--------|-------------|------------------|
| **Backend API** | 50-100 | 200+ |
| **Cart Service** | 30-60 | 150+ |
| **Order Service** | 10-20 | 50+ |
| **User Service** | 20-40 | 100+ |

#### ❌ Error Rate метрики
| Тип ошибки | Допустимый % | Критический % |
|------------|-------------|---------------|
| **HTTP 4xx** | < 1% | > 5% |
| **HTTP 5xx** | < 0.1% | > 1% |
| **Timeouts** | < 0.5% | > 2% |
| **Connection Errors** | < 0.1% | > 0.5% |

### 📊 Интеграция с Grafana

**Дашборды для нагрузочного тестирования:**

#### 🎯 Locust Performance Dashboard
- **RPS по сервисам** в реальном времени
- **Response Time распределение** (P50, P95, P99)
- **Error Rate тренды** по эндпоинтам
- **Количество активных пользователей**

#### 🏗️ System Resources Dashboard  
- **CPU Usage** по контейнерам
- **Memory Usage** и потенциальные утечки
- **Disk I/O** для Cassandra
- **Network I/O** между сервисами

#### 🗄️ Database Performance Dashboard
- **Cassandra Query Latency**
- **Connection Pool Usage**
- **Read/Write Operations** per second
- **Storage Utilization**

---

## 🔧 Генератор тестовых данных

### 📦 Создание реалистичных товаров

```python
class ProductGenerator:
    """Генератор реалистичных товаров для тестирования"""
    
    CATEGORIES = {
        "Фрукты": {
            "items": ["Яблоки", "Бананы", "Апельсины", "Груши", "Виноград"],
            "price_range": (50, 300),
            "manufacturers": ["Сады России", "ЭкоФрукт", "Фермерское хозяйство"]
        },
        "Овощи": {
            "items": ["Картофель", "Морковь", "Лук", "Помидоры", "Огурцы"],
            "price_range": (30, 150),
            "manufacturers": ["Овощной рай", "Эко-Овощи", "Фермер-продукт"]
        },
        "Молочные": {
            "items": ["Молоко", "Творог", "Сметана", "Йогурт", "Кефир"],
            "price_range": (60, 250),
            "manufacturers": ["Простоквашино", "Домик в деревне", "Веселый молочник"]
        }
    }
    
    @classmethod
    def generate_product(cls) -> dict:
        """Генерация одного реалистичного товара"""
        category_name = random.choice(list(cls.CATEGORIES.keys()))
        category_data = cls.CATEGORIES[category_name]
        
        item_name = random.choice(category_data["items"])
        manufacturer = random.choice(category_data["manufacturers"])
        
        # Реалистичные варианты названий
        variations = [
            f"{item_name} {manufacturer}",
            f"{item_name} премиум",
            f"{item_name} органические",
            f"{item_name} фермерские"
        ]
        
        price_min, price_max = category_data["price_range"]
        
        return {
            "name": random.choice(variations),
            "category": category_name,
            "price": round(random.uniform(price_min, price_max), 2),
            "stock_count": random.randint(50, 500),
            "description": f"Качественные {item_name.lower()} от {manufacturer}",
            "manufacturer": manufacturer
        }
    
    @classmethod
    def generate_batch(cls, count: int) -> List[dict]:
        """Генерация батча товаров"""
        return [cls.generate_product() for _ in range(count)]
```

### 🌱 Seed Data для тестирования

```python
class DataSeeder:
    """Заполнение базы данных тестовыми данными"""
    
    def __init__(self, admin_token: str):
        self.admin_token = admin_token
        self.headers = {"Authorization": f"Bearer {admin_token}"}
    
    async def seed_products(self, count: int = 1000):
        """Создание множества товаров для полноценного тестирования"""
        batch_size = 50
        batches = count // batch_size
        
        async with httpx.AsyncClient() as client:
            for batch_num in range(batches):
                products = ProductGenerator.generate_batch(batch_size)
                
                # Параллельное создание товаров
                tasks = [
                    client.post(
                        "http://localhost/api/products/",
                        json=product,
                        headers=self.headers
                    )
                    for product in products
                ]
                
                responses = await asyncio.gather(*tasks)
                successful = sum(1 for r in responses if r.status_code == 201)
                
                print(f"Batch {batch_num + 1}/{batches}: {successful}/{batch_size} products created")
```

---

## 🧪 Сценарии тестирования

### 🛒 Сценарий полной покупки

```python
class PurchaseScenario:
    """Комплексный сценарий покупки товаров"""
    
    @task
    def complete_purchase_flow(self):
        """Полный цикл от просмотра до заказа"""
        
        # 1. Просмотр категорий
        categories_response = self.client.get("/api/products/?category=Фрукты&limit=20", 
                                            headers=self.headers)
        
        if categories_response.status_code != 200:
            return
        
        products = categories_response.json().get("products", [])
        if not products:
            return
        
        # 2. Детальный просмотр нескольких товаров
        for _ in range(random.randint(2, 5)):
            product = random.choice(products)
            self.client.get(f"/api/products/{product['id']}", 
                           headers=self.headers)
            time.sleep(random.uniform(1, 3))  # Реалистичная пауза
        
        # 3. Добавление товаров в корзину
        selected_products = random.sample(products, min(3, len(products)))
        for product in selected_products:
            self.client.post("/cart-api/cart/items", 
                           json={
                               "product_id": product["id"],
                               "quantity": random.randint(1, 3)
                           },
                           headers=self.headers)
        
        # 4. Просмотр и модификация корзины
        cart_response = self.client.get("/cart-api/cart/", headers=self.headers)
        
        if cart_response.status_code == 200:
            cart_data = cart_response.json()
            if cart_data.get("items"):
                # Изменяем количество случайного товара
                random_item = random.choice(cart_data["items"])
                self.client.put(f"/cart-api/cart/items/{random_item['id']}", 
                              json={"quantity": random.randint(1, 5)},
                              headers=self.headers)
        
        # 5. Оформление заказа
        checkout_response = self.client.post("/cart-api/cart/checkout", 
                                           headers=self.headers)
        
        # 6. Проверка заказа
        if checkout_response.status_code == 201:
            self.client.get("/order-api/orders/", headers=self.headers)
            self.client.get("/user-api/users/me/profile", headers=self.headers)
```

### 🔐 Сценарий тестирования безопасности

```python
class SecurityTestScenario:
    """Тестирование системы безопасности под нагрузкой"""
    
    @task(3)
    def test_auth_endpoints(self):
        """Тестирование аутентификации"""
        # Валидная аутентификация
        self.client.post("/user-api/token", data={
            "username": "swagger_user",
            "password": "password123"
        })
        
        # Невалидная аутентификация (ожидается 401)
        self.client.post("/user-api/token", data={
            "username": "invalid_user",
            "password": "wrong_password"
        })
    
    @task(2)
    def test_authorization_controls(self):
        """Тестирование контроля доступа"""
        # Попытка доступа без токена (ожидается 401)
        self.client.get("/cart-api/cart/")
        
        # Попытка админского доступа обычным пользователем (ожидается 403)
        if hasattr(self, 'headers'):
            self.client.get("/cart-api/carts/", headers=self.headers)
    
    @task(1)
    def test_input_validation(self):
        """Тестирование валидации входных данных"""
        # Невалидные данные товара
        self.client.post("/cart-api/cart/items", 
                        json={"invalid": "data"},
                        headers=getattr(self, 'headers', {}))
```

---

## 📈 Анализ результатов

### 🎯 Критерии успешности тестирования

#### ✅ Отличные показатели
- **P95 Response Time** < 200ms
- **Error Rate** < 0.5%
- **Throughput** > 100 RPS
- **CPU Usage** < 70%
- **Memory Growth** стабильный

#### ⚠️ Приемлемые показатели  
- **P95 Response Time** < 500ms
- **Error Rate** < 2%
- **Throughput** > 50 RPS
- **CPU Usage** < 85%
- **Memory Growth** медленный

#### ❌ Проблемные показатели
- **P95 Response Time** > 1000ms
- **Error Rate** > 5%
- **Throughput** < 20 RPS
- **CPU Usage** > 95%
- **Memory Leaks** обнаружены

### 📊 Генерация отчетов

```bash
# HTML отчет после завершения теста
locust --headless \
       --users 100 \
       --spawn-rate 10 \
       --run-time 600s \
       --host http://localhost \
       --html locust_report.html

# CSV данные для дальнейшего анализа
locust --headless \
       --users 100 \
       --spawn-rate 10 \
       --run-time 600s \
       --host http://localhost \
       --csv locust_data
```

### 📋 Чек-лист post-тестирования

- [ ] **📊 Результаты в норме**: Все метрики в пределах целевых значений
- [ ] **🚨 Алерты сработали**: Мониторинг корректно определил нагрузку
- [ ] **🗄️ БД стабильна**: Cassandra не показывает деградации
- [ ] **💾 Нет утечек памяти**: Memory usage вернулся к нормальным значениям
- [ ] **📝 Логи проанализированы**: Критических ошибок не обнаружено
- [ ] **🔄 Система восстановилась**: Все сервисы работают нормально после теста

---

## 🔧 Оптимизация производительности

### 🎯 На основе результатов тестирования

#### 🏗️ Архитектурные улучшения
```yaml
# Горизонтальное масштабирование
backend:
  deploy:
    replicas: 3
  resources:
    limits:
      cpu: "1000m"
      memory: "1Gi"

cart-service:
  deploy:
    replicas: 2
  resources:
    limits:
      cpu: "500m"
      memory: "512Mi"
```

#### 🗄️ Оптимизация базы данных
```cql
-- Создание индексов на основе паттернов нагрузки
CREATE INDEX idx_products_category_price 
ON products (category, price);

CREATE INDEX idx_products_stock_count 
ON products (stock_count);
```

#### ⚡ Кэширование
```python
# Redis кэш для часто запрашиваемых товаров
@app.get("/api/products/{product_id}")
@cache(expire=300)  # 5 минут кэш
async def get_product(product_id: str):
    return await get_product_from_db(product_id)
```

---

## 🚨 Troubleshooting

### ❗ Распространенные проблемы

#### 🔌 Connection Refused
```log
ConnectionError: HTTPConnectionPool(host='localhost', port=80): 
Max retries exceeded with url: /api/products/
```

**Решение:**
```bash
# Проверка статуса сервисов
docker-compose ps

# Проверка логов
docker-compose logs nginx backend

# Перезапуск сервисов
docker-compose restart
```

#### 📊 High Error Rate
```log
Error rate: 15.4% (expected < 5%)
```

**Диагностика:**
```bash
# Проверка ресурсов
docker stats

# Анализ логов ошибок
docker-compose logs | grep ERROR

# Снижение нагрузки
# Уменьшите количество пользователей на 50%
```

#### 🐌 Slow Response Times
```log
P99 Response Time: 2500ms (expected < 1000ms)
```

**Оптимизация:**
1. **Увеличение ресурсов** контейнеров
2. **Оптимизация запросов** к базе данных
3. **Добавление кэширования**
4. **Горизонтальное масштабирование**

---

**🔗 Связанные разделы:**
- **[Monitoring](monitoring.md)** - Мониторинг во время нагрузочных тестов
- **[Testing](testing.md)** - Общая стратегия тестирования
- **[Architecture](architecture.md)** - Архитектурные решения для производительности
