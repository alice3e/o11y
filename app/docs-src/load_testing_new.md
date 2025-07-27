# ⚡ Нагрузочное тестирование с Locust

Система нагрузочного тестирования Product Store на базе Locust для комплексной проверки производительности всех микросервисов под реальной нагрузкой с интеграцией OpenTelemetry трейсинга.

## 🎯 Цели нагрузочного тестирования

### ✅ Основные задачи
- **📊 Оценка производительности** всех микросервисов под нагрузкой
- **🔍 Поиск bottlenecks** в архитектуре и межсервисном взаимодействии
- **🚨 Тестирование отказоустойчивости** при высокой нагрузке и ошибках
- **📈 Определение максимальной throughput capacity** системы
- **⚠️ Проверка системы мониторинга** и алертов в реальных условиях
- **🔧 Валидация горизонтального масштабирования** и load balancing
- **🎭 Эмуляция реальных пользовательских сценариев** поведения

### 🎪 Типы тестирования

#### **🟢 Smoke Testing (Базовая проверка)**
```python
# Быстрая проверка работоспособности
users = 10
duration = "2m"
ramp_up = "30s"
goal = "Verify basic functionality works"
```

#### **📊 Load Testing (Рабочая нагрузка)**
```python
# Ожидаемая production нагрузка
users = 100
duration = "10m" 
ramp_up = "2m"
goal = "Performance under expected load"
```

#### **🔥 Stress Testing (Стресс-тест)**
```python
# Нагрузка выше обычной для поиска пределов
users = 300
duration = "15m"
ramp_up = "5m"
goal = "Find breaking points and bottlenecks"
```

#### **💣 Spike Testing (Пиковые нагрузки)**
```python
# Резкие всплески трафика
users = [50, 200, 50]  # Ramp up/down pattern
duration = "10m"
goal = "Test auto-scaling and recovery"
```

#### **⏱️ Endurance Testing (Продолжительность)**
```python
# Длительная стабильная нагрузка
users = 150
duration = "2h"
goal = "Memory leaks and stability issues"
```

---

## 🏗️ Архитектура тестирования

### 🐳 Docker Integration

#### **📋 Docker Compose Configuration**
```yaml
# infra/docker-compose.yml
version: '3.8'

services:
  locust:
    image: locustio/locust:2.15.1
    ports:
      - "8089:8089"           # Web UI
      - "5557:5557"           # Worker communication
    volumes:
      - ./locust:/mnt/locust
      - ./locust/profiles:/profiles
    environment:
      - LOCUST_HOST=http://nginx
      - LOCUST_WEB_HOST=0.0.0.0
      - LOCUST_WEB_PORT=8089
      - LOCUST_LOCUSTFILE=/mnt/locust/locustfile.py
      
      # OpenTelemetry tracing integration
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318
      - OTEL_SERVICE_NAME=locust-load-test
      - OTEL_RESOURCE_ATTRIBUTES=service.name=locust,service.version=1.0.0
      
      # Prometheus metrics
      - PROMETHEUS_GATEWAY=http://prometheus:9090
      
    command: >
      locust
      --host=http://nginx
      --web-host=0.0.0.0
      --web-port=8089
      --locustfile=/mnt/locust/locustfile.py
      --html=/profiles/load_test_report.html
      --csv=/profiles/load_test_results
      --print-stats
      
    depends_on:
      - nginx
      - backend
      - cart
      - order
      - user
      - jaeger
      - prometheus
      
    networks:
      - backend
      
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8089"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 🌐 Nginx WebSocket Support

#### **⚙️ WebSocket Configuration**
```nginx
# nginx/nginx.conf - WebSocket support для Locust
upstream locust_backend {
    server locust:8089;
}

location /locust/ {
    proxy_pass http://locust_backend/;
    proxy_http_version 1.1;
    
    # WebSocket support
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # WebSocket timeouts
    proxy_read_timeout 86400;
    proxy_send_timeout 86400;
    
    # Buffer settings для real-time updates
    proxy_buffering off;
    proxy_cache off;
}

# Static files для Locust UI
location /locust/static/ {
    proxy_pass http://locust_backend/static/;
    expires 1d;
    add_header Cache-Control "public, immutable";
}
```

---

## 🛍️ Реалистичные пользовательские сценарии

### 👤 User Behavior Classes

#### **🎭 ShoppingUser - Основной класс пользователя**
```python
# infra/locust/locustfile.py
from locust import HttpUser, task, between, events
from locust.exception import RescheduleTask
import random
import uuid
import json
import time
from typing import Optional, Dict, Any

# OpenTelemetry integration
from opentelemetry import trace
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Включаем автоматический трейсинг
RequestsInstrumentor().instrument()
tracer = trace.get_tracer("locust-shopping-user")

class ShoppingUser(HttpUser):
    """Реалистичная эмуляция поведения покупателя"""
    
    # Realistic timing между actions
    wait_time = between(2, 6)  # 2-6 секунд между запросами
    
    def __init__(self, environment):
        super().__init__(environment)
        
        # User state
        self.user_id: Optional[str] = None
        self.auth_token: Optional[str] = None
        self.cart_items: Dict[str, int] = {}
        self.session_start = time.time()
        self.session_id = str(uuid.uuid4())
        
        # Behavioral parameters
        self.price_sensitivity = random.uniform(0.3, 1.0)  # 0.3 = price conscious, 1.0 = premium
        self.category_preference = random.choice([
            "Electronics", "Books", "Clothing", "Home", "Sports"
        ])
        self.purchase_likelihood = random.uniform(0.1, 0.8)  # Conversion rate variation
        
    def on_start(self):
        """Инициализация пользователя при начале сессии"""
        with tracer.start_as_current_span("user_session_start") as span:
            span.set_attribute("session.id", self.session_id)
            span.set_attribute("user.category_preference", self.category_preference)
            span.set_attribute("user.price_sensitivity", self.price_sensitivity)
            
            # Регистрация и аутентификация
            self.register_and_login()
            
            # Первоначальный просмотр главной страницы
            self.browse_homepage()
    
    def on_stop(self):
        """Завершение пользовательской сессии"""
        session_duration = time.time() - self.session_start
        
        with tracer.start_as_current_span("user_session_end") as span:
            span.set_attribute("session.duration_seconds", session_duration)
            span.set_attribute("session.cart_items", len(self.cart_items))
            span.set_attribute("session.authenticated", self.auth_token is not None)
            
        # Cleanup - logout если аутентифицирован
        if self.auth_token:
            self.logout()
    
    def register_and_login(self):
        """Регистрация и аутентификация нового пользователя"""
        username = f"loadtest_user_{self.session_id[:8]}"
        email = f"loadtest_{self.session_id[:8]}@example.com"
        password = "testpass123"
        
        with tracer.start_as_current_span("user_authentication") as span:
            # Регистрация
            register_data = {
                "username": username,
                "email": email,
                "password": password
            }
            
            register_response = self.client.post(
                "/user-api/register",
                json=register_data,
                name="🔐 User Registration"
            )
            
            if register_response.status_code == 201:
                user_data = register_response.json()
                self.user_id = user_data["id"]
                span.set_attribute("user.id", self.user_id)
                span.set_attribute("user.role", user_data.get("role", "user"))
                
                # Аутентификация
                login_data = {
                    "username": username,
                    "password": password
                }
                
                login_response = self.client.post(
                    "/user-api/login",
                    json=login_data,
                    name="🔑 User Login"
                )
                
                if login_response.status_code == 200:
                    auth_data = login_response.json()
                    self.auth_token = auth_data["access_token"]
                    span.set_attribute("auth.success", True)
                    
                    # Set authorization header для всех последующих requests
                    self.client.headers.update({
                        "Authorization": f"Bearer {self.auth_token}"
                    })
                else:
                    span.set_attribute("auth.success", False)
                    span.set_attribute("auth.error", "Login failed")
            else:
                span.set_attribute("registration.success", False)
                span.set_attribute("registration.error", register_response.text)
    
    def logout(self):
        """Выход из системы"""
        if self.auth_token:
            self.client.post("/user-api/logout", name="🚪 User Logout")
            self.auth_token = None
            self.client.headers.pop("Authorization", None)
    
    def browse_homepage(self):
        """Просмотр главной страницы и категорий"""
        with tracer.start_as_current_span("browse_homepage") as span:
            # Главная страница (через nginx)
            self.client.get("/", name="🏠 Homepage")
            
            # Получение списка категорий
            categories_response = self.client.get(
                "/api/categories",
                name="📂 Browse Categories"
            )
            
            if categories_response.status_code == 200:
                categories = categories_response.json()
                span.set_attribute("categories.count", len(categories))
                return categories
            return []

    @task(15)  # 15x weight - самая частая активность
    def browse_products(self):
        """Просмотр товаров с реалистичным поведением"""
        with tracer.start_as_current_span("browse_products") as span:
            # Выбор категории (предпочтение + случайность)
            if random.random() < 0.7:  # 70% времени - предпочитаемая категория
                category = self.category_preference
            else:
                categories = ["Electronics", "Books", "Clothing", "Home", "Sports"]
                category = random.choice(categories)
            
            span.set_attribute("browse.category", category)
            
            # Параметры пагинации
            page = random.randint(1, 3)  # Обычно пользователи смотрят первые 3 страницы
            limit = random.choice([10, 20, 50])  # Разные размеры страниц
            
            # Запрос товаров с фильтрацией
            params = {
                "category": category,
                "page": page,
                "limit": limit
            }
            
            # Иногда добавляем ценовую фильтрацию
            if random.random() < 0.3:  # 30% запросов с price filter
                if self.price_sensitivity < 0.5:  # Budget conscious
                    params["max_price"] = random.randint(500, 2000)
                else:  # Premium shoppers
                    params["min_price"] = random.randint(1000, 5000)
            
            products_response = self.client.get(
                "/api/products",
                params=params,
                name=f"🛍️ Browse Products ({category})"
            )
            
            if products_response.status_code == 200:
                products = products_response.json()
                span.set_attribute("products.found", len(products))
                
                # Просмотр деталей случайных товаров (2-5 товаров)
                view_count = min(random.randint(2, 5), len(products))
                viewed_products = random.sample(products, view_count)
                
                for product in viewed_products:
                    self.view_product_details(product)
                    
                    # Realistic delay между просмотрами
                    time.sleep(random.uniform(1, 3))
    
    def view_product_details(self, product: Dict[str, Any]):
        """Просмотр детальной информации о товаре"""
        with tracer.start_as_current_span("view_product_details") as span:
            product_id = product["id"]
            span.set_attribute("product.id", product_id)
            span.set_attribute("product.name", product["name"])
            span.set_attribute("product.price", product["price"])
            span.set_attribute("product.category", product["category"])
            
            # Запрос детальной информации
            details_response = self.client.get(
                f"/api/products/{product_id}",
                name="🔍 Product Details"
            )
            
            if details_response.status_code == 200:
                # Решение о добавлении в корзину на основе поведенческих факторов
                add_to_cart_probability = self.calculate_add_to_cart_probability(product)
                span.set_attribute("decision.add_to_cart_probability", add_to_cart_probability)
                
                if random.random() < add_to_cart_probability:
                    quantity = random.randint(1, 3)  # Realistic quantities
                    self.add_to_cart(product_id, quantity)
    
    def calculate_add_to_cart_probability(self, product: Dict[str, Any]) -> float:
        """Реалистичный расчет вероятности добавления в корзину"""
        base_probability = 0.15  # Базовая конверсия 15%
        
        # Price sensitivity adjustment
        price = float(product["price"])
        if price < 1000 and self.price_sensitivity < 0.5:  # Cheap items for budget users
            base_probability += 0.2
        elif price > 5000 and self.price_sensitivity > 0.8:  # Expensive items for premium users
            base_probability += 0.15
        elif price > 3000 and self.price_sensitivity < 0.4:  # Expensive items for budget users
            base_probability -= 0.1
        
        # Category preference boost
        if product["category"] == self.category_preference:
            base_probability += 0.1
        
        # Stock availability (if quantity shown)
        if product.get("quantity", 0) < 5:  # Low stock creates urgency
            base_probability += 0.05
        
        return min(base_probability, 0.8)  # Cap at 80%

    @task(8)   # 8x weight - средняя активность
    def manage_cart(self):
        """Управление корзиной покупок"""
        if not self.user_id:
            raise RescheduleTask()
        
        with tracer.start_as_current_span("manage_cart") as span:
            span.set_attribute("user.id", self.user_id)
            
            # Просмотр текущей корзины
            cart_response = self.client.get(
                f"/cart-api/cart/{self.user_id}",
                name="🛒 View Cart"
            )
            
            if cart_response.status_code == 200:
                cart_data = cart_response.json()
                items = cart_data.get("items", {})
                span.set_attribute("cart.items_count", len(items))
                span.set_attribute("cart.total_value", cart_data.get("total_value", 0))
                
                # Иногда обновляем количество или удаляем товары
                if items and random.random() < 0.3:  # 30% chance to modify cart
                    self.modify_cart_contents(list(items.keys()))
                
                # Возможность checkout если корзина не пустая
                if items and random.random() < self.purchase_likelihood:
                    self.attempt_checkout()
    
    def add_to_cart(self, product_id: str, quantity: int = 1):
        """Добавление товара в корзину"""
        if not self.user_id:
            return
            
        with tracer.start_as_current_span("add_to_cart") as span:
            span.set_attribute("product.id", product_id)
            span.set_attribute("cart.quantity", quantity)
            
            add_data = {
                "product_id": product_id,
                "quantity": quantity
            }
            
            response = self.client.post(
                f"/cart-api/cart/{self.user_id}/add",
                json=add_data,
                name="➕ Add to Cart"
            )
            
            if response.status_code == 200:
                self.cart_items[product_id] = quantity
                span.set_attribute("cart.add.success", True)
            else:
                span.set_attribute("cart.add.success", False)
                span.set_attribute("cart.add.error", response.text)
    
    def modify_cart_contents(self, product_ids: list):
        """Модификация содержимого корзины"""
        with tracer.start_as_current_span("modify_cart") as span:
            action = random.choice(["update_quantity", "remove_item"])
            product_id = random.choice(product_ids)
            
            span.set_attribute("cart.action", action)
            span.set_attribute("product.id", product_id)
            
            if action == "update_quantity":
                new_quantity = random.randint(1, 5)
                update_data = {
                    "product_id": product_id,
                    "quantity": new_quantity
                }
                
                response = self.client.put(
                    f"/cart-api/cart/{self.user_id}/update",
                    json=update_data,
                    name="✏️ Update Cart Quantity"
                )
                
                if response.status_code == 200:
                    self.cart_items[product_id] = new_quantity
                
            elif action == "remove_item":
                remove_data = {"product_id": product_id}
                
                response = self.client.delete(
                    f"/cart-api/cart/{self.user_id}/remove",
                    json=remove_data,
                    name="🗑️ Remove from Cart"
                )
                
                if response.status_code == 200:
                    self.cart_items.pop(product_id, None)

    @task(2)   # 2x weight - редкая активность (высокая конверсия)
    def attempt_checkout(self):
        """Попытка оформления заказа"""
        if not self.user_id or not self.cart_items:
            raise RescheduleTask()
        
        with tracer.start_as_current_span("checkout_process") as span:
            span.set_attribute("user.id", self.user_id)
            span.set_attribute("cart.items_count", len(self.cart_items))
            
            # Checkout процесс
            checkout_response = self.client.post(
                f"/cart-api/cart/{self.user_id}/checkout",
                name="💳 Checkout Cart"
            )
            
            if checkout_response.status_code == 201:
                order_data = checkout_response.json()
                order_id = order_data["id"]
                
                span.set_attribute("order.id", order_id)
                span.set_attribute("order.total_amount", order_data.get("total_amount", 0))
                span.set_attribute("checkout.success", True)
                
                # Очищаем локальную корзину
                self.cart_items.clear()
                
                # Отслеживание статуса заказа
                self.track_order_status(order_id)
                
            else:
                span.set_attribute("checkout.success", False)
                span.set_attribute("checkout.error", checkout_response.text)
    
    def track_order_status(self, order_id: str):
        """Отслеживание статуса заказа"""
        with tracer.start_as_current_span("track_order") as span:
            span.set_attribute("order.id", order_id)
            
            # Несколько проверок статуса с интервалами
            for i in range(3):
                time.sleep(random.uniform(5, 15))  # Realistic delay
                
                status_response = self.client.get(
                    f"/order-api/orders/{order_id}",
                    name="📦 Track Order Status"
                )
                
                if status_response.status_code == 200:
                    order_status = status_response.json()
                    current_status = order_status.get("status", "UNKNOWN")
                    span.set_attribute(f"order.status.check_{i+1}", current_status)
                    
                    # Прекращаем отслеживание если заказ доставлен
                    if current_status == "DELIVERED":
                        break

    @task(3)   # 3x weight - средняя активность
    def user_profile_activities(self):
        """Активности связанные с профилем пользователя"""
        if not self.user_id:
            raise RescheduleTask()
        
        with tracer.start_as_current_span("user_profile") as span:
            span.set_attribute("user.id", self.user_id)
            
            # Просмотр своего профиля
            profile_response = self.client.get(
                "/user-api/me",
                name="👤 View Profile"
            )
            
            if profile_response.status_code == 200:
                # Полный профиль с агрегированными данными
                full_profile_response = self.client.get(
                    f"/user-api/users/{self.user_id}/profile",
                    name="📊 Full Profile with Data"
                )
                
                if full_profile_response.status_code == 200:
                    profile_data = full_profile_response.json()
                    span.set_attribute("profile.total_orders", 
                                     profile_data.get("statistics", {}).get("total_orders", 0))
                    span.set_attribute("profile.total_spent", 
                                     profile_data.get("statistics", {}).get("total_spent", 0))
                
                # История заказов
                orders_response = self.client.get(
                    f"/order-api/orders/user/{self.user_id}",
                    name="📋 Order History"
                )
                
                if orders_response.status_code == 200:
                    orders = orders_response.json().get("orders", [])
                    span.set_attribute("user.order_history_count", len(orders))

    @task(1)   # 1x weight - очень редкая активность
    def admin_activities(self):
        """Административные активности (если пользователь admin)"""
        if not self.user_id or not self.auth_token:
            raise RescheduleTask()
        
        # Только для admin пользователей (первый зарегистрированный)
        if "loadtest_user_" not in str(self.user_id):
            return
            
        with tracer.start_as_current_span("admin_activities") as span:
            span.set_attribute("user.role", "admin")
            
            # Просмотр всех пользователей (admin only)
            users_response = self.client.get(
                "/user-api/users",
                name="👥 Admin: View All Users"
            )
            
            if users_response.status_code == 200:
                users = users_response.json()
                span.set_attribute("admin.users_count", len(users))
            
            # Просмотр всех заказов (admin only)
            all_orders_response = self.client.get(
                "/order-api/orders",
                name="📦 Admin: View All Orders"
            )
            
            if all_orders_response.status_code == 200:
                orders = all_orders_response.json()
                span.set_attribute("admin.orders_count", len(orders))


# Additional user types для разнообразия сценариев

class QuickBuyer(ShoppingUser):
    """Быстрый покупатель - знает что хочет"""
    wait_time = between(1, 3)  # Быстрее обычного
    
    def __init__(self, environment):
        super().__init__(environment)
        self.purchase_likelihood = 0.6  # Высокая конверсия
        self.price_sensitivity = 0.8    # Не очень чувствителен к цене
    
    @task(20)  # Больше фокуса на поиске товаров
    def quick_product_search(self):
        """Быстрый целенаправленный поиск"""
        # Прямо идет к интересующей категории
        self.browse_products()
        # Быстро принимает решения
        if self.cart_items:
            if random.random() < 0.4:  # 40% chance immediate checkout
                self.attempt_checkout()


class WindowShopper(ShoppingUser):
    """Браузер - много смотрит, мало покупает"""
    wait_time = between(3, 8)  # Медленное browsing
    
    def __init__(self, environment):
        super().__init__(environment)
        self.purchase_likelihood = 0.1  # Низкая конверсия
        self.price_sensitivity = 0.3    # Очень чувствителен к цене
    
    @task(25)  # Еще больше browsing
    def extensive_browsing(self):
        """Обширный просмотр товаров"""
        # Смотрит много категорий
        categories = ["Electronics", "Books", "Clothing", "Home", "Sports"]
        for category in random.sample(categories, 3):
            self.category_preference = category
            self.browse_products()
            time.sleep(random.uniform(2, 5))


class MobileShopper(ShoppingUser):
    """Мобильный пользователь - другие паттерны поведения"""
    wait_time = between(1, 4)  # Быстрые короткие сессии
    
    def __init__(self, environment):
        super().__init__(environment)
        self.session_duration_limit = 300  # 5 минут max session
        
    def on_start(self):
        super().on_start()
        # Добавляем mobile user agent
        self.client.headers.update({
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15"
        })
    
    @task(15)
    def mobile_browsing(self):
        """Мобильное поведение - короткие сессии"""
        # Проверяем время сессии
        if time.time() - self.session_start > self.session_duration_limit:
            self.logout()
            raise RescheduleTask()
        
        # Меньше товаров за раз (мобильный экран)
        self.browse_products()
```

---

## 📊 Metrics & Monitoring Integration

### 🎯 Custom Locust Metrics

#### **📈 Prometheus Metrics Collection**
```python
# locust_metrics.py - расширенные метрики для Locust
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from locust import events
import time

# Locust performance metrics
locust_requests_total = Counter(
    "locust_requests_total", 
    "Total requests made by Locust",
    ["method", "endpoint", "status", "user_type"]
)

locust_response_time = Histogram(
    "locust_response_time_seconds",
    "Response time histogram", 
    ["method", "endpoint", "user_type"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

locust_active_users = Gauge(
    "locust_active_users",
    "Number of active Locust users",
    ["user_type"]
)

locust_rps = Gauge(
    "locust_requests_per_second", 
    "Current requests per second"
)

locust_failures_total = Counter(
    "locust_failures_total",
    "Total failed requests",
    ["method", "endpoint", "error_type"]
)

# Business-specific metrics
user_journeys_completed = Counter(
    "user_journeys_completed_total",
    "Completed user journeys",
    ["journey_type", "outcome"]
)

cart_conversion_rate = Gauge(
    "cart_conversion_rate",
    "Cart to checkout conversion rate"
)

# Event handlers для сбора метрик
@events.request.add_listener
def record_request_metrics(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Запись метрик для каждого HTTP request"""
    
    # Определяем тип пользователя из context
    user_type = getattr(context, "user_class", "unknown").__name__ if context else "unknown"
    
    # Статус запроса
    if exception:
        status = "error"
        error_type = type(exception).__name__
        locust_failures_total.labels(
            method=request_type,
            endpoint=name, 
            error_type=error_type
        ).inc()
    else:
        status = "success"
    
    # Основные метрики
    locust_requests_total.labels(
        method=request_type,
        endpoint=name,
        status=status,
        user_type=user_type
    ).inc()
    
    locust_response_time.labels(
        method=request_type,
        endpoint=name,
        user_type=user_type
    ).observe(response_time / 1000)  # Convert ms to seconds

@events.user_count_changed.add_listener
def update_user_counts(user_count, **kwargs):
    """Обновление количества активных пользователей"""
    # Total active users
    locust_active_users.labels(user_type="total").set(user_count)

@events.init.add_listener
def start_prometheus_server(environment, **kwargs):
    """Запуск Prometheus metrics server"""
    if environment.parsed_options.master:
        start_http_server(8000)  # Metrics доступны на порту 8000

# User journey tracking
class JourneyTracker:
    def __init__(self):
        self.user_journeys = {}
    
    def start_journey(self, user_id: str, journey_type: str):
        """Начало пользовательского journey"""
        self.user_journeys[user_id] = {
            "type": journey_type,
            "start_time": time.time(),
            "steps_completed": []
        }
    
    def add_step(self, user_id: str, step: str):
        """Добавление шага в journey"""
        if user_id in self.user_journeys:
            self.user_journeys[user_id]["steps_completed"].append({
                "step": step,
                "timestamp": time.time()
            })
    
    def complete_journey(self, user_id: str, outcome: str):
        """Завершение journey"""
        if user_id in self.user_journeys:
            journey = self.user_journeys[user_id]
            duration = time.time() - journey["start_time"]
            
            user_journeys_completed.labels(
                journey_type=journey["type"],
                outcome=outcome
            ).inc()
            
            # Cleanup
            del self.user_journeys[user_id]

journey_tracker = JourneyTracker()
```

### 📊 Load Test Scenarios

#### **🎯 Test Scenarios Configuration**
```python
# scenarios.py - предопределенные сценарии тестирования
from locust import User
from locust.env import Environment

class LoadTestScenarios:
    
    @staticmethod
    def smoke_test():
        """Быстрая проверка работоспособности"""
        return {
            "user_classes": [ShoppingUser],
            "users": 10,
            "spawn_rate": 2,
            "run_time": "2m",
            "description": "Basic smoke test - verify system works"
        }
    
    @staticmethod
    def load_test():
        """Стандартный load test"""
        return {
            "user_classes": [ShoppingUser, QuickBuyer, WindowShopper],
            "users": 100,
            "spawn_rate": 5,
            "run_time": "10m",
            "description": "Standard load test - expected production traffic"
        }
    
    @staticmethod
    def stress_test():
        """Stress test для поиска пределов"""
        return {
            "user_classes": [ShoppingUser, QuickBuyer, WindowShopper, MobileShopper],
            "users": 300,
            "spawn_rate": 10,
            "run_time": "15m", 
            "description": "Stress test - find breaking points"
        }
    
    @staticmethod
    def spike_test():
        """Тест пиковых нагрузок"""
        return {
            "user_classes": [QuickBuyer, MobileShopper],  # Fast users for spike
            "users": 200,
            "spawn_rate": 50,  # Very fast ramp up
            "run_time": "5m",
            "description": "Spike test - sudden traffic increase"
        }
    
    @staticmethod
    def endurance_test():
        """Тест стабильности"""
        return {
            "user_classes": [ShoppingUser, WindowShopper],
            "users": 150,
            "spawn_rate": 3,
            "run_time": "2h",
            "description": "Endurance test - long term stability"
        }
    
    @staticmethod
    def mobile_focused_test():
        """Фокус на мобильных пользователях"""
        return {
            "user_classes": [MobileShopper],
            "users": 200,
            "spawn_rate": 8,
            "run_time": "20m",
            "description": "Mobile user behavior simulation"
        }
```

---

## 🚀 Running Load Tests

### 💻 Command Line Usage

#### **🎮 Basic Commands**
```bash
# Запуск с Web UI
docker-compose up locust
# Откройте http://localhost:8089

# Headless mode с предопределенными параметрами
docker exec -it locust locust \
    --host=http://nginx \
    --users=100 \
    --spawn-rate=5 \
    --run-time=10m \
    --headless \
    --html=/profiles/load_test_report.html \
    --csv=/profiles/results

# Distributed load testing (multiple workers)
# Master node
docker exec -it locust locust --master --host=http://nginx

# Worker nodes
docker exec -it locust locust --worker --master-host=locust-master
```

#### **📊 Advanced Testing Scenarios**
```bash
# Smoke test (быстрая проверка)
docker exec locust locust \
    --host=http://nginx \
    --users=10 \
    --spawn-rate=2 \
    --run-time=2m \
    --headless \
    --tags smoke

# Load test (рабочая нагрузка)  
docker exec locust locust \
    --host=http://nginx \
    --users=100 \
    --spawn-rate=5 \
    --run-time=10m \
    --headless \
    --tags load \
    --html=/profiles/load_test_$(date +%Y%m%d_%H%M%S).html

# Stress test (поиск пределов)
docker exec locust locust \
    --host=http://nginx \
    --users=300 \
    --spawn-rate=10 \
    --run-time=15m \
    --headless \
    --tags stress \
    --csv=/profiles/stress_test_results

# Spike test (резкие всплески)
docker exec locust locust \
    --host=http://nginx \
    --users=200 \
    --spawn-rate=50 \
    --run-time=5m \
    --headless \
    --tags spike
```

### 📈 Real-time Monitoring During Tests

#### **🔍 Grafana Integration**
```json
{
  "dashboard": {
    "title": "Load Testing - Real-time Performance",
    "panels": [
      {
        "title": "Locust RPS vs System RPS",
        "targets": [
          {
            "expr": "locust_requests_per_second",
            "legendFormat": "Locust Generated RPS"
          },
          {
            "expr": "sum(rate(http_requests_total[1m]))",
            "legendFormat": "System Actual RPS"
          }
        ]
      },
      {
        "title": "Response Time During Load Test",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(locust_response_time_seconds_bucket[1m]))",
            "legendFormat": "Locust P95 Response Time"
          },
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[1m]))",
            "legendFormat": "System P95 Response Time"
          }
        ]
      },
      {
        "title": "Error Rates",
        "targets": [
          {
            "expr": "rate(locust_failures_total[1m])",
            "legendFormat": "{{method}} {{endpoint}} failures"
          },
          {
            "expr": "rate(http_requests_total{status=~\"4..|5..\"}[1m])",
            "legendFormat": "System HTTP errors"
          }
        ]
      },
      {
        "title": "Active Users by Type",
        "targets": [
          {
            "expr": "locust_active_users",
            "legendFormat": "{{user_type}} users"
          }
        ]
      },
      {
        "title": "System Resources Under Load",
        "targets": [
          {
            "expr": "jvm_memory_heap_used{instance=\"cassandra:9103\"} / jvm_memory_heap_max * 100",
            "legendFormat": "Cassandra Heap %"
          },
          {
            "expr": "rate(nginx_http_requests_total[1m])",
            "legendFormat": "Nginx RPS"
          }
        ]
      }
    ]
  }
}
```

#### **🚨 Alert Rules для Load Testing**
```yaml
# load_test_alerts.yml
groups:
  - name: load_testing_alerts
    rules:
      - alert: LoadTestHighErrorRate
        expr: (rate(locust_failures_total[1m]) / rate(locust_requests_total[1m])) * 100 > 5
        for: 30s
        labels:
          severity: critical
          test_phase: load_testing
        annotations:
          summary: "High error rate during load test"
          description: "Error rate is {{ $value }}% during load testing"
          
      - alert: LoadTestResponseTimeDegraded
        expr: histogram_quantile(0.95, rate(locust_response_time_seconds_bucket[1m])) > 2.0
        for: 1m
        labels:
          severity: warning
          test_phase: load_testing
        annotations:
          summary: "Response times degraded under load"
          description: "P95 response time is {{ $value }}s during load test"
          
      - alert: SystemOverloadDuringTest
        expr: org_apache_cassandra_metrics_ClientRequest_Read_Latency_99thPercentile > 200
        for: 30s
        labels:
          severity: critical
          test_phase: load_testing
        annotations:
          summary: "Cassandra overloaded during test"
          description: "Cassandra P99 latency is {{ $value }}ms under load"
```

---

## 📊 Results Analysis

### 📈 Performance Metrics Collection

#### **📋 HTML Report Generation**
```html
<!-- Автоматически генерируемый HTML отчет -->
<!DOCTYPE html>
<html>
<head>
    <title>Load Test Results - {{ test_name }}</title>
    <meta charset="utf-8">
</head>
<body>
    <h1>Load Test Results</h1>
    
    <div class="summary">
        <h2>Test Summary</h2>
        <ul>
            <li>Duration: {{ test_duration }}</li>
            <li>Peak Users: {{ peak_users }}</li>
            <li>Total Requests: {{ total_requests }}</li>
            <li>Average RPS: {{ avg_rps }}</li>
            <li>Error Rate: {{ error_rate }}%</li>
        </ul>
    </div>
    
    <div class="performance">
        <h2>Performance Metrics</h2>
        <table>
            <tr>
                <th>Endpoint</th>
                <th>Requests</th>
                <th>Failures</th>
                <th>Avg (ms)</th>
                <th>P95 (ms)</th>
                <th>P99 (ms)</th>
                <th>RPS</th>
            </tr>
            <!-- Автоматически заполняется данными -->
        </table>
    </div>
    
    <div class="charts">
        <h2>Performance Charts</h2>
        <!-- Response time distribution -->
        <!-- RPS over time -->
        <!-- User count ramp up -->
        <!-- Error rate over time -->
    </div>
</body>
</html>
```

#### **📊 CSV Data Export**
```python
# Экспорт результатов в CSV для дальнейшего анализа
import csv
import json
from datetime import datetime

def export_test_results(stats, test_config):
    """Экспорт результатов тестирования"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Summary CSV
    with open(f"/profiles/test_summary_{timestamp}.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Test Name", "Duration", "Users", "Total Requests", 
            "Total Failures", "Average RPS", "Error Rate %"
        ])
        
        writer.writerow([
            test_config["name"],
            test_config["duration"], 
            test_config["users"],
            stats["total_requests"],
            stats["total_failures"],
            stats["avg_rps"],
            stats["error_rate"]
        ])
    
    # Detailed endpoint CSV
    with open(f"/profiles/endpoint_stats_{timestamp}.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Endpoint", "Method", "Requests", "Failures", 
            "Avg Response Time", "P95", "P99", "RPS"
        ])
        
        for endpoint, data in stats["endpoints"].items():
            writer.writerow([
                endpoint, data["method"], data["requests"], 
                data["failures"], data["avg_response_time"],
                data["p95"], data["p99"], data["rps"]
            ])
    
    # Performance timeline CSV
    with open(f"/profiles/timeline_{timestamp}.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Timestamp", "Active Users", "RPS", "Response Time P95", "Error Rate"
        ])
        
        for point in stats["timeline"]:
            writer.writerow([
                point["timestamp"], point["users"], point["rps"],
                point["response_time_p95"], point["error_rate"]
            ])
```

### 🎯 Performance Benchmarks

#### **📊 Expected Performance Baselines**
```yaml
# performance_baselines.yml
expected_performance:
  smoke_test:
    users: 10
    duration: "2m"
    expected_rps: 50-100
    max_p95_latency: 500ms
    max_error_rate: 1%
    
  load_test:
    users: 100 
    duration: "10m"
    expected_rps: 500-800
    max_p95_latency: 1000ms
    max_error_rate: 2%
    
  stress_test:
    users: 300
    duration: "15m"
    expected_rps: 800-1200
    max_p95_latency: 2000ms
    max_error_rate: 5%
    
# По сервисам
service_baselines:
  backend_service:
    "/api/products": 
      p95_latency: 200ms
      p99_latency: 500ms
      error_rate: 1%
      
    "/api/products/{id}":
      p95_latency: 150ms
      p99_latency: 300ms
      error_rate: 0.5%
      
  cart_service:
    "/cart-api/cart/{user_id}":
      p95_latency: 100ms
      p99_latency: 200ms
      error_rate: 1%
      
    "/cart-api/cart/{user_id}/checkout":
      p95_latency: 500ms
      p99_latency: 1000ms
      error_rate: 2%
      
  order_service:
    "/order-api/orders":
      p95_latency: 300ms
      p99_latency: 600ms
      error_rate: 1%
      
  user_service:
    "/user-api/login":
      p95_latency: 200ms
      p99_latency: 400ms
      error_rate: 0.5%
      
    "/user-api/users/{user_id}/profile":
      p95_latency: 800ms  # Includes data aggregation
      p99_latency: 1500ms
      error_rate: 2%
```

#### **🔍 Performance Analysis Scripts**
```python
# analyze_results.py
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

class LoadTestAnalyzer:
    def __init__(self, results_path: str):
        self.results_path = Path(results_path)
        self.summary_data = None
        self.endpoint_data = None
        self.timeline_data = None
        
    def load_data(self):
        """Загрузка всех CSV файлов результатов"""
        # Summary data
        summary_files = list(self.results_path.glob("test_summary_*.csv"))
        if summary_files:
            self.summary_data = pd.read_csv(summary_files[-1])
        
        # Endpoint data  
        endpoint_files = list(self.results_path.glob("endpoint_stats_*.csv"))
        if endpoint_files:
            self.endpoint_data = pd.read_csv(endpoint_files[-1])
            
        # Timeline data
        timeline_files = list(self.results_path.glob("timeline_*.csv"))
        if timeline_files:
            self.timeline_data = pd.read_csv(timeline_files[-1])
            self.timeline_data['Timestamp'] = pd.to_datetime(self.timeline_data['Timestamp'])
    
    def generate_performance_report(self):
        """Генерация отчета о производительности"""
        plt.style.use('seaborn-v0_8')
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Load Test Performance Analysis', fontsize=16)
        
        if self.timeline_data is not None:
            # RPS over time
            axes[0, 0].plot(self.timeline_data['Timestamp'], self.timeline_data['RPS'])
            axes[0, 0].set_title('Requests per Second Over Time')
            axes[0, 0].set_ylabel('RPS')
            
            # Response time over time
            axes[0, 1].plot(self.timeline_data['Timestamp'], self.timeline_data['Response Time P95'])
            axes[0, 1].set_title('P95 Response Time Over Time')
            axes[0, 1].set_ylabel('Response Time (ms)')
            
            # Error rate over time
            axes[1, 0].plot(self.timeline_data['Timestamp'], self.timeline_data['Error Rate'])
            axes[1, 0].set_title('Error Rate Over Time')
            axes[1, 0].set_ylabel('Error Rate (%)')
            
            # Active users over time
            axes[1, 1].plot(self.timeline_data['Timestamp'], self.timeline_data['Active Users'])
            axes[1, 1].set_title('Active Users Over Time')
            axes[1, 1].set_ylabel('Users')
        
        plt.tight_layout()
        plt.savefig(self.results_path / 'performance_analysis.png', dpi=300, bbox_inches='tight')
        
    def identify_bottlenecks(self):
        """Определение узких мест в производительности"""
        if self.endpoint_data is None:
            return {}
        
        bottlenecks = {}
        
        # Сортировка по P95 latency
        slow_endpoints = self.endpoint_data.nlargest(5, 'P95')
        bottlenecks['slowest_endpoints'] = slow_endpoints[['Endpoint', 'P95', 'RPS']].to_dict('records')
        
        # Высокие error rates
        error_endpoints = self.endpoint_data[self.endpoint_data['Failures'] > 0]
        error_endpoints['Error Rate'] = (error_endpoints['Failures'] / error_endpoints['Requests']) * 100
        high_error = error_endpoints[error_endpoints['Error Rate'] > 2]
        bottlenecks['high_error_endpoints'] = high_error[['Endpoint', 'Error Rate', 'Failures']].to_dict('records')
        
        # Low throughput endpoints
        low_rps = self.endpoint_data[self.endpoint_data['RPS'] < 10]
        bottlenecks['low_throughput_endpoints'] = low_rps[['Endpoint', 'RPS', 'Avg Response Time']].to_dict('records')
        
        return bottlenecks
    
    def compare_with_baseline(self, baseline_file: str):
        """Сравнение с baseline производительности"""
        baseline_data = pd.read_csv(baseline_file)
        
        comparison = {}
        for _, endpoint in self.endpoint_data.iterrows():
            endpoint_name = endpoint['Endpoint']
            baseline_row = baseline_data[baseline_data['Endpoint'] == endpoint_name]
            
            if not baseline_row.empty:
                baseline_p95 = baseline_row.iloc[0]['P95']
                current_p95 = endpoint['P95']
                
                performance_change = ((current_p95 - baseline_p95) / baseline_p95) * 100
                
                comparison[endpoint_name] = {
                    'baseline_p95': baseline_p95,
                    'current_p95': current_p95,
                    'performance_change_percent': performance_change,
                    'status': 'degraded' if performance_change > 10 else 'stable'
                }
        
        return comparison

# Использование анализатора
if __name__ == "__main__":
    analyzer = LoadTestAnalyzer("/profiles")
    analyzer.load_data()
    analyzer.generate_performance_report()
    
    bottlenecks = analyzer.identify_bottlenecks()
    print("Performance Bottlenecks:", json.dumps(bottlenecks, indent=2))
```

---

## 🔧 Best Practices

### 📋 Load Testing Guidelines

#### **🎯 Test Planning**
```yaml
# Пример плана тестирования
test_plan:
  preparation:
    - Определить production traffic patterns
    - Установить performance baselines
    - Подготовить test data (products, users)
    - Настроить мониторинг и алерты
    
  execution:
    - Начать с smoke test
    - Постепенно увеличивать нагрузку
    - Мониторить все компоненты системы
    - Документировать все наблюдения
    
  analysis:
    - Сравнить с baseline метриками
    - Идентифицировать bottlenecks
    - Проанализировать trace data в Jaeger
    - Создать action items для optimization
```

#### **⚠️ Common Pitfalls to Avoid**
```python
# ❌ BAD: Unrealistic user behavior
class BadUser(HttpUser):
    wait_time = between(0, 0)  # No think time
    
    @task
    def hammer_endpoint(self):
        # Hitting same endpoint repeatedly
        self.client.get("/api/products")

# ✅ GOOD: Realistic user simulation  
class GoodUser(HttpUser):
    wait_time = between(2, 6)  # Realistic think time
    
    @task(10)
    def browse_products(self):
        # Varied browsing patterns
        categories = self.client.get("/api/categories").json()
        category = random.choice(categories)
        self.client.get(f"/api/products?category={category}")
        
        # View product details
        products = self.client.get(f"/api/products?category={category}").json()
        if products:
            product = random.choice(products)
            self.client.get(f"/api/products/{product['id']}")
```

#### **📊 Monitoring During Tests**
```yaml
# Что мониторить во время load testing:
application_metrics:
  - Response times (P50, P95, P99)
  - Request rates (RPS)
  - Error rates (HTTP 4xx, 5xx)
  - Active connections
  
infrastructure_metrics:
  - CPU utilization
  - Memory usage
  - Disk I/O
  - Network throughput
  
database_metrics:
  - Connection pool usage
  - Query execution time
  - Queue lengths
  - Lock contention
  
business_metrics:
  - User registration rate
  - Cart conversion rate
  - Order completion rate
  - Session duration
```

### 🚀 Performance Optimization

#### **⚡ Quick Wins**
```python
# Performance optimization recommendations
optimization_checklist = {
    "connection_pooling": {
        "description": "Reuse HTTP connections",
        "implementation": "aiohttp.TCPConnector with connection limits",
        "expected_improvement": "20-30% latency reduction"
    },
    
    "async_operations": {
        "description": "Parallel processing of independent operations", 
        "implementation": "asyncio.gather() for concurrent calls",
        "expected_improvement": "40-60% response time improvement"
    },
    
    "caching": {
        "description": "Cache frequently accessed data",
        "implementation": "Redis or in-memory caching",
        "expected_improvement": "50-80% latency reduction for cached data"
    },
    
    "database_optimization": {
        "description": "Optimize Cassandra queries and indexing",
        "implementation": "Proper partition keys, prepared statements",
        "expected_improvement": "30-50% database query improvement"
    }
}
```

---

## 📚 Resources & Tools

### 🔗 Useful Links
- **[Locust Documentation](https://docs.locust.io/)** - Официальная документация
- **[OpenTelemetry Python](https://opentelemetry-python.readthedocs.io/)** - Трейсинг integration
- **[Prometheus Python Client](https://prometheus.github.io/client_python/)** - Метрики
- **[Performance Testing Best Practices](https://martinfowler.com/articles/practical-test-pyramid.html)** - Методология

### 🛠️ Additional Tools
- **[Artillery](https://artillery.io/)** - Alternative load testing tool
- **[K6](https://k6.io/)** - JavaScript-based load testing
- **[Apache Bench](https://httpd.apache.org/docs/2.4/programs/ab.html)** - Simple HTTP benchmarking
- **[Gatling](https://gatling.io/)** - High-performance load testing
