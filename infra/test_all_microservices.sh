#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Базовый URL
BASE_URL="http://localhost"

# Функция для вывода заголовков
print_header() {
    echo -e "\n${YELLOW}===== $1 =====${NC}\n"
}

# Функция для выполнения HTTP запросов с проверкой
http_request() {
    local method=$1
    local url=$2
    local headers=$3
    local data=$4
    
    echo -e "\n${YELLOW}→ $method $url${NC}"
    
    # Формируем команду curl
    local curl_cmd="curl -s -X $method"
    
    # Добавляем заголовки, если они есть
    if [ -n "$headers" ]; then
        for header in $headers; do
            curl_cmd="$curl_cmd -H \"$header\""
        done
    fi
    
    # Добавляем данные, если они есть
    if [ -n "$data" ]; then
        curl_cmd="$curl_cmd -d '$data'"
    fi
    
    # Добавляем URL
    curl_cmd="$curl_cmd $url"
    
    # Выполняем команду и выводим результат
    echo "Команда: $curl_cmd"
    local response=$(eval $curl_cmd)
    echo "Ответ: $response"
    echo "$response"
}

# Главная функция
main() {
    print_header "Тестирование микросервисов магазина"
    
    # 1. Проверка доступности сервисов
    print_header "Проверка доступности сервисов"
    
    local services=(
        "${BASE_URL}/api/system/health"
        "${BASE_URL}/cart-api/health"
        "${BASE_URL}/order-api/health"
        "${BASE_URL}/user-api/health"
    )
    
    local service_names=(
        "Backend API"
        "Cart Service"
        "Order Service"
        "User Service"
    )
    
    for i in "${!services[@]}"; do
        local response=$(curl -s -o /dev/null -w "%{http_code}" ${services[$i]})
        if [ "$response" -eq 200 ]; then
            echo -e "${GREEN}✓ ${service_names[$i]} доступен${NC}"
        else
            echo -e "${RED}✗ ${service_names[$i]} недоступен (код: $response)${NC}"
            echo -e "${RED}Тестирование остановлено. Убедитесь, что все сервисы запущены.${NC}"
            exit 1
        fi
    done
    
    # 2. Тестирование получения категорий товаров
    print_header "Тестирование API категорий"
    
    # Проверим, что API категорий работает (если реализован)
    local categories_response=$(curl -s -X GET "${BASE_URL}/api/products/categories")
    echo "Список категорий: $categories_response"
    
    # Альтернативно, получим категории из списка товаров администратором
    echo -e "\nПолучаем категории через список товаров:"
    local admin_products=$(curl -s -X GET "${BASE_URL}/api/products/" \
        -H "Authorization: Bearer swagger_admin" \
        --user "swagger_admin:admin123" || \
        curl -s -X POST "${BASE_URL}/user-api/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=swagger_admin&password=admin123" | \
        jq -r '.access_token' | xargs -I {} curl -s -X GET "${BASE_URL}/api/products/" \
        -H "Authorization: Bearer {}")
    echo "Товары для анализа категорий: $admin_products"
    
    # 3. Регистрация нового пользователя
    print_header "Регистрация нового пользователя"
    
    local username="testuser_$(date +%s)"
    local password="password123"
    
    echo -e "Создаем пользователя: $username"
    
    local register_data="{\"username\":\"$username\",\"full_name\":\"Test User\",\"phone\":\"+7 (999) 123-45-67\",\"password\":\"$password\"}"
    http_request "POST" "${BASE_URL}/user-api/users/register" "Content-Type: application/json" "$register_data"
    
    # 4. Получение токена обычного пользователя
    print_header "Получение токена обычного пользователя"
    
    local auth_data="username=$username&password=$password"
    local auth_response=$(curl -s -X POST "${BASE_URL}/user-api/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "$auth_data")
    
    echo "Ответ аутентификации: $auth_response"
    
    # Извлекаем токен
    local token=$(echo "$auth_response" | grep -o '"access_token":"[^"]*' | sed 's/"access_token":"//;s/".*//')
    
    if [ -z "$token" ]; then
        echo -e "${RED}✗ Не удалось получить токен пользователя${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ Получен токен пользователя: ${token:0:20}...${NC}"
    fi

    # 4.1. Получение токена администратора для операций с товарами
    print_header "Получение токена администратора"
    
    local admin_auth_data="username=swagger_admin&password=admin123"
    local admin_auth_response=$(curl -s -X POST "${BASE_URL}/user-api/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "$admin_auth_data")
    
    echo "Ответ аутентификации администратора: $admin_auth_response"
    
    # Извлекаем токен администратора
    local admin_token=$(echo "$admin_auth_response" | grep -o '"access_token":"[^"]*' | sed 's/"access_token":"//;s/".*//')
    
    if [ -z "$admin_token" ]; then
        echo -e "${RED}✗ Не удалось получить токен администратора${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ Получен токен администратора: ${admin_token:0:20}...${NC}"
    fi
    
    # 5. Получение профиля пользователя
    print_header "Получение профиля пользователя"
    
    local profile_response=$(curl -s -X GET "${BASE_URL}/user-api/users/me" \
        -H "Authorization: Bearer $token")
    
    echo "Профиль пользователя: $profile_response"
    
    # 6. Добавление товара (требуются права администратора)
    print_header "Добавление товара в базу данных"
    
    local product_data="{\"name\":\"Тестовый товар\",\"category\":\"Тесты\",\"price\":100.50,\"stock_count\":50}"
    local product_response=$(curl -s -X POST "${BASE_URL}/api/products/" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $admin_token" \
        -d "$product_data")
    
    echo "Ответ добавления товара: $product_response"
    
    # Извлекаем ID товара
    local product_id=$(echo "$product_response" | grep -o '"product_id":"[^"]*' | sed 's/"product_id":"//;s/".*//')
    
    if [ -z "$product_id" ]; then
        echo -e "${RED}✗ Не удалось получить ID товара${NC}"
        echo "Проверим ошибку в ответе:"
        echo "$product_response" | jq . 2>/dev/null || echo "$product_response"
        exit 1
    else
        echo -e "${GREEN}✓ Получен ID товара: $product_id${NC}"
    fi
    
    # 7. Тестирование новой функциональности контроля доступа
    print_header "Тестирование контроля доступа по ролям"
    
    # 7.1. Администратор может получить все товары
    echo "7.1. Администратор получает все товары:"
    local admin_all_products=$(curl -s -X GET "${BASE_URL}/api/products/" \
        -H "Authorization: Bearer $admin_token")
    echo "Все товары (администратор): $admin_all_products"
    
    # 7.2. Обычный пользователь НЕ может получить все товары
    echo -e "\n7.2. Обычный пользователь пытается получить все товары:"
    local user_all_products=$(curl -s -X GET "${BASE_URL}/api/products/" \
        -H "Authorization: Bearer $token")
    echo "Ответ для обычного пользователя: $user_all_products"
    
    # 7.3. Обычный пользователь может получить товары по категории
    echo -e "\n7.3. Обычный пользователь получает товары категории 'Тесты':"
    local category="Тесты"
    local encoded_category=$(printf '%s' "$category" | python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read().strip()))")
    local category_products_response=$(curl -s -X GET "${BASE_URL}/api/products/?category=$encoded_category" \
        -H "Authorization: Bearer $token")
    echo "Товары в категории $category: $category_products_response"
    
    # 7.4. Неавторизованный доступ к категории
    echo -e "\n7.4. Неавторизованный доступ к товарам категории:"
    local unauth_category_response=$(curl -s -X GET "${BASE_URL}/api/products/?category=$encoded_category")
    echo "Товары без авторизации (категория $category): $unauth_category_response"
    
    # 8. Отмечаем просмотр товара
    print_header "Отмечаем просмотр товара"
    
    local view_response=$(curl -s -X POST "${BASE_URL}/cart-api/products/$product_id/view" \
        -H "Authorization: Bearer $token")
    
    echo "Ответ отметки просмотра товара: $view_response"
    
    # 9. Получаем недавно просмотренные товары
    print_header "Получение недавно просмотренных товаров"
    
    local recent_views_response=$(curl -s -X GET "${BASE_URL}/cart-api/products/recent-views" \
        -H "Authorization: Bearer $token")
    
    echo "Недавно просмотренные товары: $recent_views_response"
    
    # 10. Добавление товара в корзину
    print_header "Добавление товара в корзину"
    
    local cart_item_data="{\"product_id\":\"$product_id\",\"quantity\":2}"
    local cart_response=$(curl -s -X POST "${BASE_URL}/cart-api/cart/items" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $token" \
        -d "$cart_item_data")
    
    echo "Ответ добавления товара в корзину: $cart_response"
    
    # 11. Получение корзины
    print_header "Получение корзины"
    
    local cart_get_response=$(curl -s -X GET "${BASE_URL}/cart-api/cart/" \
        -H "Authorization: Bearer $token")
    
    echo "Корзина: $cart_get_response"
    
    # 12. Тестирование рекомендаций на основе просмотров
    print_header "Получение рекомендаций на основе просмотров"
    
    local recommendations_response=$(curl -s -X GET "${BASE_URL}/cart-api/products/recommendations" \
        -H "Authorization: Bearer $token")
    
    echo "Рекомендации: $recommendations_response"
    
    # 13. Оформление заказа
    print_header "Оформление заказа"
    
    local checkout_response=$(curl -s -X POST "${BASE_URL}/cart-api/cart/checkout" \
        -H "Authorization: Bearer $token")
    
    echo "Ответ оформления заказа: $checkout_response"
    
    # 14. Получение списка заказов
    print_header "Получение списка заказов"
    
    local orders_response=$(curl -s -X GET "${BASE_URL}/user-api/users/me/orders" \
        -H "Authorization: Bearer $token")
    
    echo "Список заказов: $orders_response"
    
    # 15. Добавление товара в корзину для тестов обновления и удаления
    print_header "Добавление товара в корзину для тестов обновления и удаления"
    local cart_item_data="{\"product_id\":\"$product_id\",\"quantity\":1}"
    local cart_response=$(curl -s -X POST "${BASE_URL}/cart-api/cart/items" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $token" \
        -d "$cart_item_data")
    echo "Ответ добавления товара в корзину: $cart_response"
    local item_id=$(echo "$cart_response" | grep -o '"id":"[^"]*' | sed 's/"id":"//;s/".*//')

    # 16. Обновление количества товара в корзине
    print_header "Обновление количества товара в корзине"
    if [ -z "$item_id" ]; then
        echo -e "${RED}✗ Не удалось получить ID товара в корзине для обновления${NC}"
    else
        local update_cart_data="{\"quantity\":3}"
        local update_cart_response=$(curl -s -X PUT "${BASE_URL}/cart-api/cart/items/$item_id" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $token" \
            -d "$update_cart_data")
        echo "Ответ обновления корзины: $update_cart_response"
    fi

    # 17. Удаление товара из корзины
    print_header "Удаление товара из корзины"
    if [ -z "$item_id" ]; then
        echo -e "${RED}✗ Не удалось получить ID товара в корзине для удаления${NC}"
    else
        local delete_cart_response=$(curl -s -X DELETE "${BASE_URL}/cart-api/cart/items/$item_id" \
            -H "Authorization: Bearer $token")
        echo "Ответ удаления товара из корзины: $delete_cart_response"
    fi

    # 18. Попытка оформления пустого заказа
    print_header "Попытка оформления пустого заказа"
    # Очистим корзину перед этим тестом
    local clear_cart_response=$(curl -s -X DELETE "${BASE_URL}/cart-api/cart/" \
        -H "Authorization: Bearer $token")
    echo "Ответ очистки корзины: $clear_cart_response"
    local empty_checkout_response=$(curl -s -X POST "${BASE_URL}/cart-api/cart/checkout" \
        -H "Authorization: Bearer $token")
    echo "Ответ оформления пустого заказа: $empty_checkout_response"

    # 19. Обновление профиля пользователя
    print_header "Обновление профиля пользователя"
    local new_full_name="Updated Test User"
    local new_phone="+79999876543"
    local update_user_response=$(curl -s -X PUT "${BASE_URL}/user-api/users/me" \
        -H "Authorization: Bearer $token" \
        -F "full_name=$new_full_name" \
        -F "phone=$new_phone")
    echo "Ответ обновления профиля: $update_user_response"
    # Проверим, что данные обновились
    local updated_profile_response=$(curl -s -X GET "${BASE_URL}/user-api/users/me" \
        -H "Authorization: Bearer $token")
    echo "Обновленный профиль: $updated_profile_response"

    # 20. Получение полного профиля пользователя (с корзиной и заказами)
    print_header "Получение полного профиля пользователя"
    local full_profile_response=$(curl -s -X GET "${BASE_URL}/user-api/users/me/profile" \
        -H "Authorization: Bearer $token")
    echo "Полный профиль пользователя: $full_profile_response"

    # 21. Проверка несуществующего эндпоинта
    print_header "Проверка несуществующего эндпоинта"
    local not_found_response=$(curl -s -w "%{http_code}" -o /dev/null "${BASE_URL}/api/non-existent-endpoint")
    if [ "$not_found_response" -eq 404 ]; then
        echo -e "${GREEN}✓ Сервер корректно вернул 404 Not Found${NC}"
    else
        echo -e "${RED}✗ Сервер вернул код $not_found_response вместо 404${NC}"
    fi

    # 22. Добавление нескольких товаров для тестирования фильтрации (требуются права администратора)
    print_header "Добавление тестовых товаров для фильтрации"
    
    # Создаем массив товаров с разными ценами
    local products=(
        "{\"name\":\"Молоко 'Простоквашино'\",\"category\":\"Молочные продукты\",\"price\":89.90,\"stock_count\":30}"
        "{\"name\":\"Творог 'Домик в деревне'\",\"category\":\"Молочные продукты\",\"price\":129.50,\"stock_count\":20}"
        "{\"name\":\"Сыр 'Российский'\",\"category\":\"Молочные продукты\",\"price\":349.99,\"stock_count\":15}"
        "{\"name\":\"Йогурт 'Активия'\",\"category\":\"Молочные продукты\",\"price\":59.90,\"stock_count\":40}"
    )
    
    for product_data in "${products[@]}"; do
        echo "Добавление товара: $product_data"
        local product_response=$(curl -s -X POST "${BASE_URL}/api/products/" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $admin_token" \
            -d "$product_data")
        echo "Ответ: $product_response"
    done

    # 23. Тестирование контроля доступа при фильтрации
    print_header "Тестирование контроля доступа при фильтрации товаров"
    
    echo "Обычный пользователь получает товары категории 'Молочные продукты':"
    local milk_category="Молочные продукты"
    local encoded_milk_category=$(printf '%s' "$milk_category" | python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read().strip()))")
    local user_filtered_response=$(curl -s -X GET "${BASE_URL}/api/products/?category=$encoded_milk_category" \
        -H "Authorization: Bearer $token")
    echo "Фильтрация обычным пользователем: $user_filtered_response"
    # 24. Тестирование фильтрации (обновленный API)
    print_header "Тестирование фильтрации товаров"
    
    # Создаем несколько товаров для тестирования
    echo "Создаем товары для тестирования фильтрации..."
    local milk_product_data="{\"name\":\"Молоко тестовое\",\"category\":\"Молочные продукты\",\"price\":250.00,\"stock_count\":30}"
    curl -s -X POST "${BASE_URL}/api/products/" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $admin_token" \
        -d "$milk_product_data" > /dev/null
    
    # Теперь фильтруем по категории "Молочные продукты"
    local filtered_products_response=$(curl -s -X GET "${BASE_URL}/api/products/?category=$encoded_milk_category" \
        -H "Authorization: Bearer $token")
    echo "Товары категории 'Молочные продукты': $filtered_products_response"
    
    # 25. Тестирование получения всех товаров администратором
    print_header "Тестирование получения всех товаров администратором"
    
    local all_products_response=$(curl -s -X GET "${BASE_URL}/api/products" \
        -H "Authorization: Bearer $admin_token")
    echo "Все товары (администратор): $all_products_response"
    
    # 26. Удаление тестовых товаров (требуются права администратора)
    print_header "Удаление добавленных товаров"
    
    # Получаем список всех товаров как администратор
    local all_products_response=$(curl -s -X GET "${BASE_URL}/api/products" \
        -H "Authorization: Bearer $admin_token")
    
    # Извлекаем ID всех товаров
    local product_ids=$(echo "$all_products_response" | grep -o '"product_id":"[^"]*' | sed 's/"product_id":"//;s/".*//')
    
    for id in $product_ids; do
        echo "Удаление товара с ID: $id"
        local delete_product_response=$(curl -s -w "%{http_code}" -o /dev/null -X DELETE "${BASE_URL}/api/products/$id" \
            -H "Authorization: Bearer $admin_token")
        echo "Код ответа: $delete_product_response"
    done
    
    print_header "Все тесты завершены"
}

# Запуск главной функции
main 