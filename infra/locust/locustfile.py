# Файл: infra/locust/locustfile.py

import random
import logging
import uuid
from locust import HttpUser, task, between
from json import JSONDecodeError

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
    cart_items: dict = {}

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
        "пролистывает" несколько страниц и открывает детальную страницу товара.
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
        limit_per_page = 20 # Сколько товаров на одной странице
        current_skip = 0
        total_pages = 1
        products_on_last_page = []

        url = f"/api/products/?category={category_name}&skip={current_skip}&limit={limit_per_page}"
        with self.client.get(url, headers=self.headers, catch_response=True, name="/api/products/?category=[category]") as response:
            try:
                if response.status_code != 200:
                    response.failure(f"Failed to browse initial page for category {category_name}")
                    return
                
                data = response.json()
                total_pages = data.get("pages", 1)
                products_on_last_page = data.get("items", [])
                
            except JSONDecodeError:
                response.failure("Non-JSON response for initial product list")
                return

        # --- Шаг 3: Определяем, сколько страниц "пролистать" ---
        pages_to_scroll = random.randint(0, 5) # Пролистает от 0 до 4 ДОПОЛНИТЕЛЬНЫХ страниц
        
        if total_pages > 1: # Только если есть куда листать
            for i in range(pages_to_scroll):
                current_skip += limit_per_page
                
                # Защита, чтобы не выйти за пределы существующих страниц
                if current_skip >= (total_pages * limit_per_page):
                    break

                # Имитация паузы между пролистыванием страниц
                self.wait()

                scroll_url = f"/api/products/?category={category_name}&skip={current_skip}&limit={limit_per_page}"
                with self.client.get(scroll_url, headers=self.headers, catch_response=True, name="/api/products/?category=[category]") as response:
                    try:
                        if response.status_code != 200:
                            # Это не критичная ошибка, просто прекращаем листать
                            break 
                        
                        data = response.json()
                        products = data.get("items", [])
                        
                        if not products: # Если страница пустая, прекращаем
                            break
                        
                        products_on_last_page = products

                    except JSONDecodeError:
                        break # Прекращаем, если ответ не JSON

        # --- Шаг 4: Выбираем случайный товар с последней просмотренной страницы ---
        if not products_on_last_page:
            return

        product_to_view = random.choice(products_on_last_page)
        print(products_on_last_page)
        product_id = product_to_view.get("product_id")
        if not product_id:
            return
            
        # Запоминаем ID товара для будущих действий (добавление в корзину)
        self.viewed_product_ids.append(product_id)
        self.viewed_product_ids = self.viewed_product_ids[-20:] # Ограничиваем историю

        # --- Шаг 5: Открываем детальную карточку товара ---
        self.client.get(f"/api/products/{product_id}", headers=self.headers, name="/api/products/[product_id]")
        
    @task(5)
    def manage_cart(self):
        """Работа с корзиной: добавление, просмотр, изменение/удаление."""
        if not self.token or not self.viewed_product_ids: return
            
        product_id_to_add = random.choice(self.viewed_product_ids)
        
        with self.client.post(
            "/cart-api/cart/items",
            headers=self.headers,
            json={"product_id": product_id_to_add, "quantity": random.randint(1, 3)},
            catch_response=True,
            name="/cart-api/cart/items (add)"
        ) as response:
            try:
                if response.status_code == 200:
                    item_data = response.json()
                    self.cart_items[item_data["id"]] = item_data["product_id"]
                else:
                    response.failure("Failed to add item to cart")
                    return
            except (JSONDecodeError, KeyError):
                response.failure("Failed to parse cart item from response.")
                return

        self.client.get("/cart-api/cart/", headers=self.headers, name="/cart-api/cart/ (view)")
        
        if self.cart_items and random.random() < 0.3:
            random_item_id = random.choice(list(self.cart_items.keys()))
            
            if random.random() < 0.5:
                with self.client.delete(f"/cart-api/cart/items/{random_item_id}", headers=self.headers, name="/cart-api/cart/items/[item_id] (delete)") as response:
                    if response.status_code == 200:
                        del self.cart_items[random_item_id]
            else:
                self.client.put(
                    f"/cart-api/cart/items/{random_item_id}",
                    headers=self.headers,
                    json={"quantity": random.randint(1, 10)},
                    name="/cart-api/cart/items/[item_id] (update)"
                )

    @task(1)
    def checkout_and_check_orders(self):
        """Оформление заказа и проверка истории."""
        if not self.token or not self.cart_items: return
            
        # ИСПРАВЛЕНИЕ: Используем эндпоинт из user-service, как в документации
        with self.client.post("/user-api/users/me/orders", headers=self.headers, catch_response=True, name="/user-api/users/me/orders (checkout)") as response:
            try:
                if response.status_code == 200:
                    logging.info(f"User {self.username} successfully checked out.")
                    self.cart_items.clear()
                else:
                    response.failure(f"Checkout failed. Status: {response.status_code}, Text: {response.text}")
                    return
            except JSONDecodeError:
                response.failure("Non-JSON response on checkout")
                return

        # Небольшая пауза перед проверкой заказов
        self.interrupt(reschedule=False)
        self.wait()
        
        self.client.get("/user-api/users/me/orders", headers=self.headers, name="/user-api/users/me/orders (view)")
        self.client.get("/user-api/users/me/profile", headers=self.headers, name="/user-api/users/me/profile")