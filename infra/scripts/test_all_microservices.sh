#!/bin/bash

# Скрипт для добавления 5000 товаров в базу данных через 50 администраторов.
# Использует curl для взаимодействия с API.

set -e # Завершить скрипт при ошибке

echo "Начало скрипта добавления товаров..."

# --- Конфигурация ---
BASE_URL="http://localhost"
USER_SERVICE_URL="${BASE_URL}/user-api"
BACKEND_SERVICE_URL="${BASE_URL}/api"

# Используем встроенные учетные данные swagger_admin для создания новых админов
SWAGGER_ADMIN_USERNAME="swagger_admin"
SWAGGER_ADMIN_PASSWORD="admin123"

# --- Определение категорий и названий продуктов ---
CATEGORIES=(
    "Фрукты" "Овощи" "Молочные продукты" "Напитки" "Бакалея" 
    "Мясо" "Сладкое" "Пельмени" "Средства для уборки" "Сигареты" "Алкоголь"
)

# Ассоциативный массив имен продуктов по категориям
declare -A PRODUCT_NAMES
PRODUCT_NAMES["Фрукты"]="Яблоки Бананы Апельсины Груши Киви Манго Ананас"
PRODUCT_NAMES["Овощи"]="Морковь Картофель Лук Томаты Огурцы Капуста Перец"
PRODUCT_NAMES["Молочные продукты"]="Молоко Творог Сыр Йогурт Кефир Сметана"
PRODUCT_NAMES["Напитки"]="Кока-кола Спрайт Фанта Вода Сок Чай Кофе"
PRODUCT_NAMES["Бакалея"]="Хлеб Макароны Рис Гречка Мука Сахар Соль"
PRODUCT_NAMES["Мясо"]="Говядина Свинина Курица Индейка Колбаса Сосиски"
PRODUCT_NAMES["Сладкое"]="Шоколад Конфеты Печенье Торт Мороженое Вафли"
PRODUCT_NAMES["Пельмени"]="Пельмени_мясные Вареники Манты Хинкали Равиоли"
PRODUCT_NAMES["Средства для уборки"]="Порошок Мыло Шампунь Моющее_средство"
PRODUCT_NAMES["Сигареты"]="Marlboro Parliament Lucky_Strike Camel"
PRODUCT_NAMES["Алкоголь"]="Водка Вино Пиво Коньяк Виски"

# --- Функция для получения токена администратора ---
get_admin_token() {
    local username="$1"
    local password="$2"

    # echo "Получение токена для пользователя: $username"
    local response
    response=$(curl -s -X POST "${USER_SERVICE_URL}/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=${username}&password=${password}")

    # Проверка на ошибки в ответе
    if echo "$response" | grep -q '"access_token"'; then
        echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])"
        return 0
    else
        echo "Ошибка получения токена для $username: $response" >&2
        return 1
    fi
}

# --- Функция для регистрации нового пользователя ---
register_user() {
    local username="$1"
    local password="$2"
    local full_name="$3"
    local phone="$4"

    # echo "Регистрация пользователя: $username"
    local response_code
    response_code=$(curl -s -w "%{http_code}" -o /tmp/reg_response.txt -X POST "${USER_SERVICE_URL}/users/register" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"${username}\", \"full_name\":\"${full_name}\", \"phone\":\"${phone}\", \"password\":\"${password}\"}")

    if [ "$response_code" -eq 200 ]; then
        echo "Пользователь $username успешно зарегистрирован."
        return 0
    elif [ "$response_code" -eq 400 ]; then
         # Проверим, действительно ли пользователь уже существует
         if grep -q "already registered" /tmp/reg_response.txt; then
             echo "Пользователь $username уже существует. Продолжаем..."
             return 0
         else
             echo "Ошибка регистрации пользователя $username (400):"
             cat /tmp/reg_response.txt
             return 1
         fi
    else
         echo "Ошибка регистрации пользователя $username. HTTP код: $response_code"
         cat /tmp/reg_response.txt
         return 1
    fi
}

# --- Функция для добавления товара ---
add_product() {
    local token="$1"
    local name="$2"
    local category="$3"
    local price="$4"
    local quantity="$5"

    # echo "Добавление товара: $name"
    local response_code
    response_code=$(curl -s -w "%{http_code}" -o /tmp/product_response.txt -X POST "${BACKEND_SERVICE_URL}/products/" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${token}" \
        -d "{\"name\":\"${name}\", \"category\":\"${category}\", \"price\":${price}, \"quantity\":${quantity}}")

    if [ "$response_code" -eq 200 ] || [ "$response_code" -eq 201 ]; then
        # echo "Товар '$name' успешно добавлен."
        return 0
    else
        echo "Ошибка добавления товара '$name'. HTTP код: $response_code"
        cat /tmp/product_response.txt
        return 1
    fi
}

# --- Основная логика ---

# 1. Получить токен swagger_admin для проверки доступности
echo "Получение токена для swagger_admin..."
SWAGGER_ADMIN_TOKEN=$(get_admin_token "$SWAGGER_ADMIN_USERNAME" "$SWAGGER_ADMIN_PASSWORD")
if [ $? -ne 0 ] || [ -z "$SWAGGER_ADMIN_TOKEN" ]; then
    echo "Не удалось получить токен для swagger_admin. Завершение."
    exit 1
fi
echo "Токен swagger_admin получен."

# 2. Создать 50 администраторов (имена начинаются с admin_, поэтому они автоматически становятся админами)
echo "Создание 50 администраторов..."
for i in $(seq 1 50); do
    ADMIN_USERNAME="admin_$i"
    ADMIN_PASSWORD="adminpass_$i"
    ADMIN_FULL_NAME="Admin User $i"
    ADMIN_PHONE="+799900000$i" # Простой формат номера

    # Пытаемся зарегистрировать админа.
    register_user "$ADMIN_USERNAME" "$ADMIN_PASSWORD" "$ADMIN_FULL_NAME" "$ADMIN_PHONE"
    if [ $? -ne 0 ]; then
        echo "Ошибка при регистрации $ADMIN_USERNAME. Продолжаем..."
    fi
done
echo "Создание администраторов завершено (или уже существовали)."

# 3. Добавить 5000 товаров
echo "Начало добавления 5000 товаров..."
TOTAL_PRODUCTS=5000
PRODUCTS_PER_ADMIN=$((TOTAL_PRODUCTS / 50)) # 100 товаров на админа

product_counter=1
error_counter=0
max_errors=10 # Максимальное количество ошибок перед остановкой

for admin_num in $(seq 1 50); do
    ADMIN_USERNAME="admin_$admin_num"
    ADMIN_PASSWORD="adminpass_$admin_num"

    echo "Получение токена для администратора $ADMIN_USERNAME..."
    ADMIN_TOKEN=""
    ADMIN_TOKEN=$(get_admin_token "$ADMIN_USERNAME" "$ADMIN_PASSWORD")
    if [ $? -ne 0 ] || [ -z "$ADMIN_TOKEN" ]; then
        echo "Не удалось получить токен для администратора $ADMIN_USERNAME. Пропуск администратора."
        ((error_counter++))
        if [ "$error_counter" -ge "$max_errors" ]; then
            echo "Достигнуто максимальное количество ошибок ($max_errors). Завершение."
            exit 1
        fi
        continue
    fi
    echo "Токен для администратора $ADMIN_USERNAME получен."

    echo "Администратор $ADMIN_USERNAME добавляет $PRODUCTS_PER_ADMIN товаров..."

    for ((j=1; j<=PRODUCTS_PER_ADMIN; j++)); do
        # Выбираем случайную категорию
        category_index=$((RANDOM % ${#CATEGORIES[@]}))
        category="${CATEGORIES[$category_index]}"

        # Получаем список имен для категории
        IFS=' ' read -r -a product_names_array <<< "${PRODUCT_NAMES[$category]}"
        # Выбираем случайное имя из списка
        product_name_index=$((RANDOM % ${#product_names_array[@]}))
        base_product_name="${product_names_array[$product_name_index]}"

        # Формируем уникальное имя продукта
        product_name="${base_product_name} ${product_counter}"

        # Генерируем случайные цена и количество
        # Цена от 10.00 до 1000.00
        price_int=$((RANDOM % 99001 + 1000)) # 1000 до 100000
        price=$(echo "scale=2; $price_int / 100" | bc)
        # Количество от 1 до 1000
        quantity=$((RANDOM % 1000 + 1))

        # Добавляем товар
        if add_product "$ADMIN_TOKEN" "$product_name" "$category" "$price" "$quantity"; then
             # Выводим прогресс каждые 100 товаров
             if (( product_counter % 100 == 0 )); then
                echo "Добавлено товаров: $product_counter"
             fi
             ((product_counter++))
        else
            echo "Ошибка при добавлении товара $product_counter."
            ((error_counter++))
            if [ "$error_counter" -ge "$max_errors" ]; then
                echo "Достигнуто максимальное количество ошибок ($max_errors). Завершение."
                exit 1
            fi
            # Продолжаем добавлять другие товары
        fi

        # Добавим небольшую задержку, чтобы не перегружать сервис (опционально)
        # sleep 0.005
    done

    echo "Администратор $ADMIN_USERNAME завершил добавление товаров."
done

echo "Скрипт завершен. Всего попыток добавления товаров: $((product_counter-1))"
echo "Количество ошибок: $error_counter"

