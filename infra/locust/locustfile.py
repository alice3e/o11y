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
        """Просмотр товаров: категории -> список -> карточка товара."""
        if not self.token: return

        with self.client.get("/api/products/categories/list", headers=self.headers, catch_response=True, name="/api/products/categories/list") as response:
            try:
                categories = response.json()
                if not categories or response.status_code != 200:
                    response.failure("Failed to get categories list or list is empty")
                    return
            except JSONDecodeError:
                response.failure("Non-JSON response for categories list")
                return
        
        category_name = random.choice(categories)["name"]
        
        url = f"/api/products/?category={category_name}&limit=20"
        with self.client.get(url, headers=self.headers, catch_response=True, name="/api/products/?category=[category]") as response:
            try:
                products_data = response.json()
                if response.status_code != 200:
                    response.failure(f"Failed to browse category {category_name}")
                    return
                products = products_data.get("items", [])
                if not products: return
            except JSONDecodeError:
                response.failure("Non-JSON response for product list")
                return

        product_to_view = random.choice(products)
        product_id = product_to_view.get("product_id")
        if not product_id: return
            
        self.viewed_product_ids.append(product_id)
        self.viewed_product_ids = self.viewed_product_ids[-20:]

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