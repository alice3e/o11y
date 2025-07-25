# Файл: infra/locust/locustfile.py

import random
import logging
import uuid
from locust import HttpUser, task, between
from json import JSONDecodeError
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.requests import RequestsInstrumentor

trace.set_tracer_provider(
    TracerProvider(
        resource=Resource.create({"service.name": "locust"})
    )
)
span_processor = BatchSpanProcessor(
    OTLPSpanExporter(endpoint="http://jaeger:4318/v1/traces")
)

trace.get_tracer_provider().add_span_processor(span_processor)
RequestsInstrumentor().instrument()

# --- Настройка логирования для чистоты вывода ---
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)

class ShoppingUser(HttpUser):
    """
    Моделирует поведение обычного покупателя в интернет-магазине.
    Сценарий включает:
    1. Регистрацию и вход (один раз при старте).
    2. Просмотр категорий и товаров (самое частое действие).
    3. Добавление товаров в корзину и управление ею.
    4. Оформление заказа и проверку истории (самое редкое действие).
    """
    wait_time = between(2, 6)
    
    # --- Состояние, уникальное для каждого виртуального пользователя ---
    token: str = None
    headers: dict = {}
    username: str = None
    viewed_product_ids: list = []
    cart_items: list = []

    def on_start(self):
        """
        Выполняется один раз для каждого пользователя.
        Регистрирует пользователя и получает JWT-токен.
        """
        unique_id = uuid.uuid4().hex[:8]
        self.username = f"customer_{unique_id}"
        password = f"password_{unique_id}"
        
        user_data = {
            "username": self.username,
            "full_name": f"Load Test User {unique_id}",
            "phone": f"+7999{random.randint(1000000, 9999999)}",
            "password": password
        }
        
        with self.client.post("/user-api/users/register", json=user_data, catch_response=True, name="/user-api/users/register") as response:
            if response.status_code not in [200, 201]:
                response.failure(f"Failed to register user. Status: {response.status_code}, Text: {response.text}")
                self.environment.runner.quit() # Если регистрация не удалась, пользователь бесполезен

        with self.client.post("/user-api/token", data={"username": self.username, "password": password}, catch_response=True, name="/user-api/token") as response:
            try:
                if response.status_code == 200:
                    self.token = response.json()["access_token"]
                    self.headers = {"Authorization": f"Bearer {self.token}"}
                    logging.info(f"User {self.username} successfully logged in.")
                else:
                    response.failure(f"Failed to login. Status: {response.status_code}, Text: {response.text}")
            except (JSONDecodeError, KeyError):
                response.failure("Failed to parse login token from response.")

    @task(10)
    def browse_products(self):
        """
        Имитирует просмотр товаров: получает список категорий, выбирает одну,
        "прыгает" по случайным страницам от 1 до 5 раз,
        а затем открывает детальную карточку случайного товара из просмотренных.
        """
        if not self.token:
            return

        # --- Шаг 1: Получаем список категорий ---
        with self.client.get("/api/products/categories/list", headers=self.headers, catch_response=True, name="/api/products/categories/list") as response:
            try:
                if response.status_code != 200:
                    response.failure("Failed to get categories list")
                    return
                categories = response.json()
                if not categories:
                    return
            except JSONDecodeError:
                response.failure("Non-JSON response for categories list")
                return
        
        category_name = random.choice(categories)["name"]
        
        # --- Шаг 2: Делаем первый запрос, чтобы узнать, сколько всего страниц ---
        limit_per_page = 20
        total_pages = 1
        viewable_products = [] # Список для накопления товаров со всех просмотренных страниц

        url = f"/api/products/?category={category_name}&skip=0&limit={limit_per_page}"
        with self.client.get(url, headers=self.headers, catch_response=True, name="/api/products/?category=[category]") as response:
            try:
                if response.status_code != 200:
                    response.failure(f"Failed to browse initial page for category {category_name}")
                    return
                
                data = response.json()
                total_pages = data.get("pages", 1)
                # Добавляем товары с первой страницы в наш накопительный список
                if data.get("items"):
                    viewable_products.extend(data["items"])
                
            except JSONDecodeError:
                response.failure("Non-JSON response for initial product list")
                return

        # --- Шаг 3: Определяем, сколько раз "прыгнуть" по страницам ---
        jumps_to_make = random.randint(1, 5)
        
        if total_pages > 1:
            for _ in range(jumps_to_make):
                # Генерируем случайный номер страницы (от 0 до total_pages-1)
                random_page_index = random.randint(0, total_pages - 1)
                random_skip = random_page_index * limit_per_page

                # Пауза перед "прыжком" на новую страницу
                self.wait()

                jump_url = f"/api/products/?category={category_name}&skip={random_skip}&limit={limit_per_page}"
                with self.client.get(jump_url, headers=self.headers, catch_response=True, name="/api/products/?category=[category]") as response:
                    try:
                        if response.status_code != 200:
                            continue # Если страница не загрузилась, просто переходим к следующему прыжку
                        
                        data = response.json()
                        products_on_page = data.get("items", [])
                        
                        if products_on_page:
                            viewable_products.extend(products_on_page)

                    except JSONDecodeError:
                        continue # Игнорируем ошибки парсинга и пробуем следующую страницу

        # --- Шаг 4: Выбираем случайный товар из всех, что мы видели ---
        if not viewable_products:
            return

        product_to_view = random.choice(viewable_products)
        product_id = product_to_view.get("product_id")
        if not product_id:
            return
            
        # Запоминаем ID товара для будущих действий
        self.viewed_product_ids.append(product_id)
        self.viewed_product_ids = self.viewed_product_ids[-20:]

        # --- Шаг 5: Открываем детальную карточку товара ---
        self.client.get(f"/api/products/{product_id}", headers=self.headers, name="/api/products/[product_id]")
        
    @task(5)
    def manage_cart(self):
        """
        Работа с корзиной: добавление, просмотр и изменение/удаление на основе
        АКТУАЛЬНОГО состояния корзины с сервера.
        """
        if not self.token:
            return

        # --- ШАГ 1: С вероятностью 70% пытаемся добавить новый товар ---
        # Это основное действие пользователя с корзиной
        if random.random() < 0.7 and self.viewed_product_ids:
            product_id_to_add = random.choice(self.viewed_product_ids)
            
            with self.client.post(
                "/cart-api/cart/items",
                headers=self.headers,
                json={"product_id": product_id_to_add, "quantity": random.randint(1, 3)},
                catch_response=True,
                name="/cart-api/cart/items (add)"
            ) as response:
                try:
                    # Независимо от успеха, мы не обновляем локальное состояние,
                    # так как не будем на него полагаться.
                    if response.status_code != 200:
                        response.failure("Failed to add item to cart")
                except JSONDecodeError:
                    response.failure("Non-JSON response when adding to cart.")
        
        # --- ШАГ 2: Получаем АКТУАЛЬНОЕ состояние корзины с сервера ---
        current_cart_items = []
        with self.client.get("/cart-api/cart/", headers=self.headers, catch_response=True, name="/cart-api/cart/ (view)") as response:
            try:
                if response.status_code == 200:
                    cart_data = response.json()
                    current_cart_items = cart_data.get("items", [])
                else:
                    response.failure("Failed to get current cart state")
                    return # Если не можем получить корзину, нет смысла продолжать
            except (JSONDecodeError, KeyError):
                response.failure("Failed to parse current cart state")
                return

        # --- ШАГ 3: Если в корзине ЕСТЬ товары, с вероятностью 50% изменяем/удаляем один из них ---
        if current_cart_items and random.random() < 0.5:
            # Выбираем случайный товар из АКТУАЛЬНОГО списка
            item_to_modify = random.choice(current_cart_items)
            product_id_to_modify = item_to_modify.get("product_id")

            if not product_id_to_modify:
                return

            # 50% шанс на удаление
            if random.random() < 0.5:
                self.client.delete(
                    f"/cart-api/cart/items/{product_id_to_modify}", 
                    headers=self.headers, 
                    name="/cart-api/cart/items/[product_id] (delete)"
                )
            # 50% шанс на обновление
            else:
                self.client.put(
                    f"/cart-api/cart/items/{product_id_to_modify}",
                    headers=self.headers,
                    json={"quantity": random.randint(1, 10)},
                    name="/cart-api/cart/items/[product_id] (update)"
                )
        
        self.cart_items = [item.get("product_id") for item in current_cart_items if item.get("product_id")]
        

    @task(1)
    def checkout_and_check_orders(self):
        """
        Гарантированно оформляет заказ и проверяет историю.
        Если корзина пуста, сначала добавляет в нее товар.
        """
        if not self.token:
            return

        # --- Шаг 1: Проверяем актуальное состояние корзины на сервере ---
        cart_is_empty = True
        with self.client.get("/cart-api/cart/", headers=self.headers, catch_response=True, name="/cart-api/cart/ (pre-checkout check)") as response:
            try:
                if response.status_code == 200:
                    cart_data = response.json()
                    if cart_data.get("items"):
                        cart_is_empty = False
                else:
                    response.failure("Failed to check cart state before checkout")
                    return # Не можем продолжить, если не знаем состояние корзины
            except (JSONDecodeError, KeyError):
                response.failure("Could not parse cart state response")
                return

        # --- Шаг 2: Если корзина пуста, добавляем товар ---
        if cart_is_empty:
            if not self.viewed_product_ids:
                # Если пользователь ничего не смотрел, он не может ничего добавить. Выходим.
                return

            product_id_to_add = random.choice(self.viewed_product_ids)
            with self.client.post(
                "/cart-api/cart/items",
                headers=self.headers,
                json={"product_id": product_id_to_add, "quantity": 1},
                catch_response=True,
                name="/cart-api/cart/items (add before checkout)"
            ) as response:
                try:
                    if response.status_code == 200:
                        item_data = response.json()
                        self.cart_items.append(item_data.get("product_id"))
                    else:
                        response.failure("Failed to add pre-checkout item to cart")
                        return # Если не смогли добавить товар, то и checkout невозможен
                except (JSONDecodeError, KeyError):
                    response.failure("Failed to parse pre-checkout item response")
                    return

        # --- Шаг 3: Оформляем заказ ---
        # Теперь мы уверены, что в корзине что-то есть
        with self.client.post("/user-api/users/me/orders", headers=self.headers, catch_response=True, name="/user-api/users/me/orders (checkout)") as response:
            try:
                if response.status_code == 200:
                    logging.info(f"User {self.username} successfully checked out.")
                    self.cart_items.clear() # Очищаем наше локальное состояние
                else:
                    response.failure(f"Checkout failed. Status: {response.status_code}, Text: {response.text}")
                    return # Если checkout не удался, нет смысла проверять заказы
            except JSONDecodeError:
                response.failure("Non-JSON response on checkout")
                return

        # --- Шаг 4: Пауза и проверка истории заказов ---
        # ИСПРАВЛЕНИЕ: Используем self.wait() для имитации паузы
        self.wait()
        
        self.client.get("/user-api/users/me/orders", headers=self.headers, name="/user-api/users/me/orders (view)")
        self.client.get("/user-api/users/me/profile", headers=self.headers, name="/user-api/users/me/profile")