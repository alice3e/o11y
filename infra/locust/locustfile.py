import random
import logging
from locust import HttpUser, task, between, events

# --- Настройка ---
# Отключаем "шумные" логи от http-клиента, чтобы видеть только важную информацию
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)


# --- Вспомогательные функции и данные ---
# Используем демо-пользователей, создаваемых вашим user-service
REGULAR_USER_CREDS = {"username": "swagger_user", "password": "password123"}
ADMIN_CREDS = {"username": "swagger_admin", "password": "admin123"}
CATEGORIES = ["Фрукты", "Овощи", "Молочные продукты", "Напитки", "Бакалея", "Мясо", "Сладкое", "Пельмени", "Средсва для уборки", "Сигареты", "Алкоголь"]


class BaseShopUser(HttpUser):
    """
    Базовый класс для всех пользователей магазина.
    Содержит общую логику, например, аутентификацию.
    Абстрактный класс - Locust не будет его запускать.
    """
    abstract = True
    token = None
    headers = {}

    def login(self, creds):
        """Выполняет вход и сохраняет токен."""
        try:
            with self.client.post(
                "/user-api/token",
                data=creds,
                catch_response=True, # type: ignore
                name="/user-api/token" # type: ignore
            ) as response:
                if response.status_code == 200:
                    self.token = response.json()["access_token"]
                    self.headers = {"Authorization": f"Bearer {self.token}"}
                    logging.info(f"User {creds['username']} logged in successfully.")
                else:
                    response.failure(f"Failed to login user {creds['username']}. Status: {response.status_code}, Body: {response.text}")
        except Exception as e:
            logging.error(f"Login request failed for {creds['username']}: {e}")

class RegularUser(BaseShopUser):
    """
    Симулирует поведение обычного покупателя.
    Вес 10 означает, что на каждых 11 пользователей будет 10 обычных и 1 админ.
    """
    weight = 10
    wait_time = between(1, 4)  # Пауза между действиями от 1 до 4 секунд

    # Атрибуты для хранения состояния сессии пользователя
    viewed_product_ids = []
    cart_items = {} # {item_id: product_id}

    def on_start(self):
        """Выполняется при старте каждого виртуального пользователя."""
        self.login(REGULAR_USER_CREDS)

    @task(15)
    def browse_and_view_product(self):
        """Сценарий: просмотр категорий и затем конкретного товара."""
        if not self.token:
            logging.warning("Skipping task, no token.")
            return

        category = random.choice(CATEGORIES)
        with self.client.get(
            f"/api/products/?category={category}",
            headers=self.headers,
            name="/api/products/?category=[category]", # type: ignore
            catch_response=True # type: ignore
        ) as response:
            if response.status_code == 200:
                # --- ИСПРАВЛЕНИЕ ОШИБКИ KeyError ---
                products_list = response.json()

                # Убеждаемся, что получили непустой список
                if products_list and isinstance(products_list, list):
                    product = random.choice(products_list)
                    product_id = product.get("id")
                    if product_id:
                        # Сохраняем только последние 10 просмотренных ID, чтобы список не рос бесконечно
                        self.viewed_product_ids.append(product_id)
                        self.viewed_product_ids = self.viewed_product_ids[-10:]

                        self.client.get(
                            f"/api/products/{product_id}",
                            headers=self.headers,
                            name="/api/products/[product_id]" # type: ignore
                        )
                # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
            else:
                response.failure(f"Failed to get products for category {category}. Status: {response.status_code}")

    @task(5)
    def add_to_cart(self):
        """Добавляет в корзину один из ранее просмотренных товаров."""
        if not self.token or not self.viewed_product_ids:
            return
        
        product_id = random.choice(self.viewed_product_ids)
        with self.client.post(
            "/cart-api/cart/items",
            headers=self.headers,
            json={"product_id": product_id, "quantity": random.randint(1, 3)},
            name="/cart-api/cart/items", # type: ignore
            catch_response=True # type: ignore
        ) as response:
            if response.status_code == 200:
                response.success()
                # Обновляем наше локальное представление корзины
                cart_data = response.json()
                for item in cart_data.get("items", []):
                    if item["product_id"] == product_id:
                        self.cart_items[item["id"]] = item["product_id"]
            else:
                response.failure(f"Failed to add product {product_id} to cart")

    @task(2)
    def update_or_delete_cart_item(self):
        """Изменяет количество товара в корзине или удаляет его."""
        if not self.token or not self.cart_items:
            return
        
        item_id_to_modify = random.choice(list(self.cart_items.keys()))

        if random.random() < 0.2: # 20% шанс удалить товар
            with self.client.delete(
                f"/cart-api/cart/items/{item_id_to_modify}",
                headers=self.headers,
                name="/cart-api/cart/items/[item_id]", # type: ignore
                catch_response=True # type: ignore
            ) as response:
                if response.status_code == 200:
                    response.success()
                    del self.cart_items[item_id_to_modify] # Удаляем из локального представления
                else:
                    response.failure(f"Failed to delete item {item_id_to_modify}")
        else: # 80% шанс обновить количество
            self.client.put(
                f"/cart-api/cart/items/{item_id_to_modify}",
                headers=self.headers,
                json={"quantity": random.randint(1, 5)},
                name="/cart-api/cart/items/[item_id]" # type: ignore
            )

    @task(1)
    def checkout(self):
        """Оформляет заказ."""
        if not self.token or not self.cart_items:
            return

        with self.client.post(
            "/cart-api/cart/checkout",
            headers=self.headers,
            name="/cart-api/cart/checkout", # type: ignore
            catch_response=True # type: ignore
        ) as response:
            if response.status_code == 200:
                response.success()
                self.cart_items = {} # Очищаем корзину после успешного заказа
            else:
                response.failure(f"Failed to checkout. Status: {response.status_code}, Body: {response.text}")

    @task(1)
    def view_profile_and_orders(self):
        """Редко просматривает свой профиль и историю заказов."""
        if not self.token:
            return
        self.client.get("/user-api/users/me/profile", headers=self.headers, name="/user-api/users/me/profile") # type: ignore
        self.client.get("/user-api/users/me/orders", headers=self.headers, name="/user-api/users/me/orders") # type: ignore

class AdminUser(BaseShopUser):
    """
    Симулирует поведение администратора.
    """
    weight = 1
    wait_time = between(3, 10) # Админы думают дольше

    def on_start(self):
        self.login(ADMIN_CREDS)

    @task(10)
    def check_all_products_and_update(self):
        """Просматривает все товары и, возможно, обновляет один из них."""
        if not self.token:
            return

        with self.client.get(
            "/api/products/",
            headers=self.headers,
            name="/api/products/ (admin)", # type: ignore
            catch_response=True # type: ignore
        ) as response:
            if response.status_code == 200:
                response.success()
                products = response.json()
                if products and isinstance(products, list) and random.random() < 0.3: # 30% шанс обновить товар
                    product_to_update = random.choice(products)
                    self.client.put(
                        f"/api/products/{product_to_update['id']}",
                        headers=self.headers,
                        json={
                            "name": product_to_update['name'],
                            "category": product_to_update['category'],
                            "price": round(product_to_update.get('price', 10.0) * random.uniform(0.9, 1.1), 2),
                            "quantity": product_to_update.get('quantity', 0) + random.randint(-5, 20)
                        },
                        name="/api/products/[product_id] (update)" # type: ignore
                    )
            else:
                response.failure(f"Failed to get all products as admin. Status: {response.status_code}")

    @task(3)
    def add_new_product(self):
        """Добавляет новый товар."""
        if not self.token:
            return
        
        new_product = {
            "name": f"New Gadget {random.randint(1000, 9999)}",
            "category": "Electronics",
            "price": round(random.uniform(50, 500), 2),
            "quantity": random.randint(10, 100)
        }
        self.client.post("/api/products/", headers=self.headers, json=new_product, name="/api/products/ (create)") # type: ignore

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Событие, которое срабатывает при старте теста."""
    logging.info("--- Starting Load Test ---")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Событие, которое срабатывает при остановке теста."""
    logging.info("--- Load Test Finished ---")