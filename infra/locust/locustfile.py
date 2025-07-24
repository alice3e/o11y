import random
import logging
import time
import threading
from locust import HttpUser, task, between, events

# --- Настройка логирования ---
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)

# --- Глобальные переменные для контроля фаз ---
current_phase = 1
products_count = 0
phase_lock = threading.Lock()
registered_admins = []
registered_users = []

# --- Константы ---
TARGET_PRODUCTS = 5000
CATEGORIES = [
    "Фрукты", "Овощи", "Молочные продукты", "Напитки", "Бакалея", 
    "Мясо", "Сладкое", "Пельмени", "Средства для уборки", "Сигареты", "Алкоголь"
]

PRODUCT_NAMES = {
    "Фрукты": ["Яблоки", "Бананы", "Апельсины", "Груши", "Киви", "Манго", "Ананас"],
    "Овощи": ["Морковь", "Картофель", "Лук", "Томаты", "Огурцы", "Капуста", "Перец"],
    "Молочные продукты": ["Молоко", "Творог", "Сыр", "Йогурт", "Кефир", "Сметана"],
    "Напитки": ["Кока-кола", "Спрайт", "Фанта", "Вода", "Сок", "Чай", "Кофе"],
    "Бакалея": ["Хлеб", "Макароны", "Рис", "Гречка", "Мука", "Сахар", "Соль"],
    "Мясо": ["Говядина", "Свинина", "Курица", "Индейка", "Колбаса", "Сосиски"],
    "Сладкое": ["Шоколад", "Конфеты", "Печенье", "Торт", "Мороженое", "Вафли"],
    "Пельмени": ["Пельмени мясные", "Вареники", "Манты", "Хинкали", "Равиоли"],
    "Средства для уборки": ["Порошок", "Мыло", "Шампунь", "Моющее средство"],
    "Сигареты": ["Marlboro", "Parliament", "Lucky Strike", "Camel"],
    "Алкоголь": ["Водка", "Вино", "Пиво", "Коньяк", "Виски"]
}


def check_products_count(client, headers):
    """Проверяет количество товаров в БД"""
    global products_count
    try:
        response = client.get("/api/products/", headers=headers)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and 'items' in data:
                products_count = data.get('total', 0)
            elif isinstance(data, list):
                products_count = len(data)
            logging.info(f"Current products count: {products_count}")
            return products_count
    except Exception as e:
        logging.error(f"Error checking products count: {e}")
    return 0


class BaseUser(HttpUser):
    """Базовый класс для всех пользователей"""
    abstract = True
    token = None
    headers = {}
    username = None

    def register_user(self, username, password, is_admin=False):
        """Регистрирует нового пользователя"""
        user_data = {
            "username": username,
            "full_name": f"User {username}",
            "phone": f"+7{random.randint(9000000000, 9999999999)}",
            "password": password
        }
        
        try:
            response = self.client.post("/user-api/users/register", json=user_data)
            if response.status_code in [200, 201]:
                logging.info(f"User {username} registered successfully")
                return True
            else:
                logging.warning(f"Failed to register {username}: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logging.error(f"Registration error for {username}: {e}")
            return False

    def login(self, username, password):
        """Выполняет вход и сохраняет токен"""
        creds = {"username": username, "password": password}
        try:
            response = self.client.post("/user-api/token", data=creds)
            if response.status_code == 200:
                self.token = response.json()["access_token"]
                self.headers = {"Authorization": f"Bearer {self.token}"}
                self.username = username
                logging.info(f"User {username} logged in successfully")
                return True
            else:
                logging.warning(f"Failed to login {username}: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"Login error for {username}: {e}")
            return False


class DynamicUser(BaseUser):
    """Универсальный пользователь, который меняет поведение в зависимости от фазы"""
    weight = 1
    wait_time = between(0.5, 3)
    
    user_role = None  # 'admin', 'user', 'customer'
    viewed_products = []
    cart_items = {}

    def on_start(self):
        global current_phase, registered_admins, registered_users
        
        # Определяем роль пользователя в зависимости от фазы
        if current_phase == 1:
            # Фаза 1: становимся админом если нужно больше админов
            if len(registered_admins) < 3:  # Ограничиваем количество админов
                self.become_admin()
            else:
                self.wait_for_next_phase()
                
        elif current_phase == 2:
            # Фаза 2: регистрируемся как обычный пользователь
            if len(registered_users) < 50:
                self.become_user()
            else:
                self.wait_for_next_phase()
                
        elif current_phase == 3:
            # Фаза 3: выбираем роль в зависимости от потребностей
            if len(registered_users) > 0:
                if random.random() < 0.1 and len(registered_admins) > 0:  # 10% админов
                    self.become_existing_admin()
                else:  # 90% покупателей
                    self.become_existing_customer()
            else:
                self.wait_for_next_phase()
    
    def become_admin(self):
        """Становится администратором"""
        global registered_admins
        admin_num = len(registered_admins) + 1
        username = f"admin_{admin_num}_{random.randint(1000, 9999)}"
        password = "admin123"
        
        if self.register_user(username, password, is_admin=True):
            if self.login(username, password):
                with phase_lock:
                    registered_admins.append(username)
                    self.user_role = 'admin'
                logging.info(f"✅ New admin created: {username}")
    
    def become_user(self):
        """Регистрируется как обычный пользователь"""
        global registered_users, current_phase
        user_num = len(registered_users) + 1
        username = f"user_{user_num}_{random.randint(1000, 9999)}"
        password = "user123"
        
        if self.register_user(username, password):
            if self.login(username, password):
                with phase_lock:
                    registered_users.append(username)
                    self.user_role = 'user'
                    
                    # Проверяем переход к фазе 3
                    if len(registered_users) >= 50:
                        if current_phase == 2:
                            current_phase = 3
                            logging.info(f"🎉 PHASE 2 COMPLETE! Users registered: {len(registered_users)}. Moving to PHASE 3...")
                
                logging.info(f"✅ New user registered: {username}")
    
    def become_existing_customer(self):
        """Становится существующим покупателем"""
        global registered_users
        if registered_users:
            username = random.choice(registered_users)
            password = "user123"
            
            if self.login(username, password):
                self.user_role = 'customer'
                logging.info(f"🛒 Customer {username} started shopping")
    
    def become_existing_admin(self):
        """Становится существующим админом"""
        global registered_admins
        if registered_admins:
            username = random.choice(registered_admins)
            password = "admin123"
            
            if self.login(username, password):
                self.user_role = 'admin'
                logging.info(f"🔧 Admin {username} started maintenance")
    
    def wait_for_next_phase(self):
        """Ожидает следующей фазы"""
        self.user_role = 'waiting'

    @task(20)
    def execute_role_task(self):
        """Выполняет задачи в зависимости от роли и фазы"""
        global current_phase
        
        if self.user_role == 'admin' and current_phase == 1:
            self.admin_add_products()
        elif self.user_role == 'user' and current_phase == 2:
            self.user_wait()
        elif self.user_role == 'customer' and current_phase == 3:
            self.customer_browse_and_shop()
        elif self.user_role == 'admin' and current_phase == 3:
            self.admin_maintain_stock()
        elif self.user_role == 'waiting':
            self.wait_for_role_assignment()
    
    def admin_add_products(self):
        """Админская задача: добавление товаров в фазе 1"""
        global current_phase, products_count
        
        if not self.token:
            return
            
        # Проверяем количество товаров
        current_count = check_products_count(self.client, self.headers)
        
        if current_count >= TARGET_PRODUCTS:
            with phase_lock:
                if current_phase == 1:
                    current_phase = 2
                    logging.info(f"🎉 PHASE 1 COMPLETE! Products added: {current_count}. Moving to PHASE 2...")
            return
        
        # Добавляем товары пачками
        for _ in range(5):  # Добавляем по 5 товаров за раз
            category = random.choice(CATEGORIES)
            product_names = PRODUCT_NAMES.get(category, ["Generic Product"])
            base_name = random.choice(product_names)
            
            product_data = {
                "name": f"{base_name} {random.randint(1, 999)}",
                "category": category,
                "price": round(random.uniform(10, 1000), 2),
                "stock_count": random.randint(50, 500)
            }
            
            try:
                response = self.client.post("/api/products/", headers=self.headers, json=product_data)
                if response.status_code not in [200, 201]:
                    logging.error(f"Failed to create product: {response.status_code} - {response.text}")
            except Exception as e:
                logging.error(f"Error creating product: {e}")
    
    def user_wait(self):
        """Пользователь ожидает фазы 3"""
        time.sleep(2)
    
    def customer_browse_and_shop(self):
        """Покупательская активность в фазе 3"""
        if not self.token:
            return
            
        # Выбираем случайную активность
        activity = random.choice(['browse', 'add_to_cart', 'modify_cart', 'checkout', 'check_orders'])
        
        if activity == 'browse':
            self.browse_products()
        elif activity == 'add_to_cart' and self.viewed_products:
            self.add_to_cart()
        elif activity == 'modify_cart' and self.cart_items:
            self.modify_cart()
        elif activity == 'checkout' and self.cart_items:
            self.checkout()
        elif activity == 'check_orders':
            self.check_orders()
    
    def admin_maintain_stock(self):
        """Админская задача: поддержание товаров в фазе 3"""
        if not self.token:
            return
            
        if random.random() < 0.7:  # 70% пополнение товаров
            self.restock_products()
        else:  # 30% добавление новых товаров
            self.add_new_products()
    
    def wait_for_role_assignment(self):
        """Ожидание назначения роли"""
        global current_phase
        time.sleep(2)
        
        # Пытаемся переназначить роль только если фаза изменилась
        if current_phase == 2 and self.user_role == 'waiting' and len(registered_users) < 50:
            self.become_user()
        elif current_phase == 3 and self.user_role == 'waiting':
            if len(registered_users) > 0:
                if random.random() < 0.1 and len(registered_admins) > 0:
                    self.become_existing_admin()
                else:
                    self.become_existing_customer()

    # Методы из старых классов (с небольшими изменениями)
    def browse_products(self):
        """Просматривает товары по категориям"""
        category = random.choice(CATEGORIES)
        try:
            response = self.client.get(f"/api/products/?category={category}", headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', []) if isinstance(data, dict) else data
                
                if items and isinstance(items, list):
                    product = random.choice(items)
                    product_id = product.get("product_id") or product.get("id")
                    if product_id:
                        self.viewed_products.append(product_id)
                        self.viewed_products = self.viewed_products[-20:]
                        
                        # Просматриваем детали товара
                        self.client.get(f"/api/products/{product_id}", headers=self.headers)
        except Exception as e:
            logging.error(f"Error browsing products: {e}")

    def add_to_cart(self):
        """Добавляет товары в корзину"""
        if not self.viewed_products:
            return
            
        product_id = random.choice(self.viewed_products)
        cart_data = {
            "product_id": product_id,
            "quantity": random.randint(1, 5)
        }
        
        try:
            response = self.client.post("/cart-api/cart/items", headers=self.headers, json=cart_data)
            if response.status_code in [200, 201]:
                cart_response = response.json()
                if isinstance(cart_response, dict) and 'items' in cart_response:
                    for item in cart_response['items']:
                        if item.get('product_id') == product_id:
                            self.cart_items[item.get('id')] = product_id
        except Exception as e:
            logging.error(f"Error adding to cart: {e}")

    def modify_cart(self):
        """Изменяет количество товаров в корзине"""
        if not self.cart_items:
            return
            
        item_id = random.choice(list(self.cart_items.keys()))
        
        if random.random() < 0.3:  # 30% удаляем
            try:
                response = self.client.delete(f"/cart-api/cart/items/{item_id}", headers=self.headers)
                if response.status_code == 200:
                    del self.cart_items[item_id]
            except Exception as e:
                logging.error(f"Error deleting cart item: {e}")
        else:  # 70% обновляем количество
            update_data = {"quantity": random.randint(1, 10)}
            try:
                self.client.put(f"/cart-api/cart/items/{item_id}", headers=self.headers, json=update_data)
            except Exception as e:
                logging.error(f"Error updating cart item: {e}")

    def checkout(self):
        """Оформляет заказ"""
        try:
            response = self.client.post("/cart-api/cart/checkout", headers=self.headers)
            if response.status_code in [200, 201]:
                self.cart_items = {}
                logging.info(f"Order completed by {self.username}")
        except Exception as e:
            logging.error(f"Error during checkout: {e}")

    def check_orders(self):
        """Проверяет свои заказы"""
        try:
            self.client.get("/user-api/users/me/orders", headers=self.headers)
            self.client.get("/user-api/users/me/profile", headers=self.headers)
        except Exception as e:
            logging.error(f"Error checking orders: {e}")

    def restock_products(self):
        """Пополняет товары которые заканчиваются"""
        try:
            response = self.client.get("/api/products/", headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', []) if isinstance(data, dict) else data
                
                if items:
                    low_stock_products = [
                        p for p in items 
                        if isinstance(p, dict) and p.get('stock_count', 0) < 20
                    ]
                    
                    if low_stock_products:
                        product = random.choice(low_stock_products)
                        product_id = product.get('product_id') or product.get('id')
                        
                        updated_data = {
                            "name": product.get('name'),
                            "category": product.get('category'),
                            "price": product.get('price'),
                            "stock_count": product.get('stock_count', 0) + random.randint(50, 200)
                        }
                        
                        self.client.put(f"/api/products/{product_id}", headers=self.headers, json=updated_data)
                        logging.info(f"Restocked product {product.get('name')}")
        except Exception as e:
            logging.error(f"Error restocking products: {e}")

    def add_new_products(self):
        """Добавляет новые товары"""
        category = random.choice(CATEGORIES)
        product_names = PRODUCT_NAMES.get(category, ["New Product"])
        base_name = random.choice(product_names)
        
        product_data = {
            "name": f"{base_name} Premium {random.randint(100, 999)}",
            "category": category,
            "price": round(random.uniform(50, 2000), 2),
            "stock_count": random.randint(20, 100)
        }
        
        try:
            response = self.client.post("/api/products/", headers=self.headers, json=product_data)
            if response.status_code in [200, 201]:
                logging.info(f"Added new product: {product_data['name']}")
        except Exception as e:
            logging.error(f"Error adding new product: {e}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Событие старта тестирования"""
    global current_phase
    logging.info("🚀 STARTING 3-PHASE LOAD TEST")
    logging.info("📋 PHASE 1: Admins will add products until 5000+ items")
    logging.info("📋 PHASE 2: Users will register")
    logging.info("📋 PHASE 3: Full shopping simulation")
    current_phase = 1


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Событие завершения тестирования"""
    logging.info("🏁 LOAD TEST COMPLETED")
    logging.info(f"Final phase: {current_phase}")
    logging.info(f"Products created: {products_count}")
    logging.info(f"Admins registered: {len(registered_admins)}")
    logging.info(f"Users registered: {len(registered_users)}")


def log_phase_status():
    """Периодически логирует статус фаз"""
    def status_logger():
        while True:
            time.sleep(30)  # Каждые 30 секунд
            logging.info(f"📊 STATUS - Phase: {current_phase}, Products: {products_count}, "
                        f"Admins: {len(registered_admins)}, Users: {len(registered_users)}")
    
    status_thread = threading.Thread(target=status_logger, daemon=True)
    status_thread.start()

# Запускаем логирование статуса
log_phase_status()
