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
        "${BASE_URL}/cart-api/"
        "${BASE_URL}/order-api/"
        "${BASE_URL}/user-api/"
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
    
    # 2. Регистрация нового пользователя
    print_header "Регистрация нового пользователя"
    
    local username="testuser_$(date +%s)"
    local password="password123"
    
    echo -e "Создаем пользователя: $username"
    
    local register_data="{\"username\":\"$username\",\"full_name\":\"Test User\",\"phone\":\"+7 (999) 123-45-67\",\"password\":\"$password\"}"
    http_request "POST" "${BASE_URL}/user-api/users/register" "Content-Type: application/json" "$register_data"
    
    # 3. Получение токена
    print_header "Получение токена"
    
    local auth_data="username=$username&password=$password"
    local auth_response=$(curl -s -X POST "${BASE_URL}/user-api/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "$auth_data")
    
    echo "Ответ аутентификации: $auth_response"
    
    # Извлекаем токен
    local token=$(echo "$auth_response" | grep -o '"access_token":"[^"]*' | sed 's/"access_token":"//;s/".*//')
    
    if [ -z "$token" ]; then
        echo -e "${RED}✗ Не удалось получить токен${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ Получен токен: $token${NC}"
    fi
    
    # 4. Получение профиля пользователя
    print_header "Получение профиля пользователя"
    
    local profile_response=$(curl -s -X GET "${BASE_URL}/user-api/users/me" \
        -H "Authorization: Bearer $token")
    
    echo "Профиль пользователя: $profile_response"
    
    # 5. Добавление товара
    print_header "Добавление товара в базу данных"
    
    local product_data="{\"name\":\"Тестовый товар\",\"category\":\"Тесты\",\"price\":100.50,\"quantity\":50}"
    local product_response=$(curl -s -X POST "${BASE_URL}/api/products/" \
        -H "Content-Type: application/json" \
        -d "$product_data")
    
    echo "Ответ добавления товара: $product_response"
    
    # Извлекаем ID товара
    local product_id=$(echo "$product_response" | grep -o '"id":"[^"]*' | sed 's/"id":"//;s/".*//')
    
    if [ -z "$product_id" ]; then
        echo -e "${RED}✗ Не удалось получить ID товара${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ Получен ID товара: $product_id${NC}"
    fi
    
    # 6. Добавление товара в корзину
    print_header "Добавление товара в корзину"
    
    local cart_item_data="{\"product_id\":\"$product_id\",\"quantity\":2}"
    local cart_response=$(curl -s -X POST "${BASE_URL}/cart-api/cart/items" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $token" \
        -d "$cart_item_data")
    
    echo "Ответ добавления товара в корзину: $cart_response"
    
    # 7. Получение корзины
    print_header "Получение корзины"
    
    local cart_get_response=$(curl -s -X GET "${BASE_URL}/cart-api/cart/" \
        -H "Authorization: Bearer $token")
    
    echo "Корзина: $cart_get_response"
    
    # 8. Оформление заказа
    print_header "Оформление заказа"
    
    local checkout_response=$(curl -s -X POST "${BASE_URL}/cart-api/cart/checkout" \
        -H "Authorization: Bearer $token")
    
    echo "Ответ оформления заказа: $checkout_response"
    
    # 9. Получение списка заказов
    print_header "Получение списка заказов"
    
    local orders_response=$(curl -s -X GET "${BASE_URL}/user-api/users/me/orders" \
        -H "Authorization: Bearer $token")
    
    echo "Список заказов: $orders_response"
    
    # 10. Добавление товара в корзину для тестов обновления и удаления
    print_header "Добавление товара в корзину для тестов обновления и удаления"
    local cart_item_data="{\"product_id\":\"$product_id\",\"quantity\":1}"
    local cart_response=$(curl -s -X POST "${BASE_URL}/cart-api/cart/items" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $token" \
        -d "$cart_item_data")
    echo "Ответ добавления товара в корзину: $cart_response"
    local item_id=$(echo "$cart_response" | grep -o '"id":"[^"]*' | sed 's/"id":"//;s/".*//')

    # 11. Обновление количества товара в корзине
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

    # 12. Удаление товара из корзины
    print_header "Удаление товара из корзины"
    if [ -z "$item_id" ]; then
        echo -e "${RED}✗ Не удалось получить ID товара в корзине для удаления${NC}"
    else
        local delete_cart_response=$(curl -s -X DELETE "${BASE_URL}/cart-api/cart/items/$item_id" \
            -H "Authorization: Bearer $token")
        echo "Ответ удаления товара из корзины: $delete_cart_response"
    fi

    # 13. Попытка оформления пустого заказа
    print_header "Попытка оформления пустого заказа"
    # Очистим корзину перед этим тестом
    local clear_cart_response=$(curl -s -X DELETE "${BASE_URL}/cart-api/cart/" \
        -H "Authorization: Bearer $token")
    echo "Ответ очистки корзины: $clear_cart_response"
    local empty_checkout_response=$(curl -s -X POST "${BASE_URL}/cart-api/cart/checkout" \
        -H "Authorization: Bearer $token")
    echo "Ответ оформления пустого заказа: $empty_checkout_response"

    # 14. Обновление профиля пользователя
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

    # 15. Получение полного профиля пользователя (с корзиной и заказами)
    print_header "Получение полного профиля пользователя"
    local full_profile_response=$(curl -s -X GET "${BASE_URL}/user-api/users/me/profile" \
        -H "Authorization: Bearer $token")
    echo "Полный профиль пользователя: $full_profile_response"

    # 16. Проверка несуществующего эндпоинта
    print_header "Проверка несуществующего эндпоинта"
    local not_found_response=$(curl -s -w "%{http_code}" -o /dev/null "${BASE_URL}/api/non-existent-endpoint")
    if [ "$not_found_response" -eq 404 ]; then
        echo -e "${GREEN}✓ Сервер корректно вернул 404 Not Found${NC}"
    else
        echo -e "${RED}✗ Сервер вернул код $not_found_response вместо 404${NC}"
    fi

    # 17. Добавление еще одного товара
    print_header "Добавление второго товара в базу данных"
    local product_data_2="{\"name\":\"Второй тестовый товар\",\"category\":\"Тесты 2\",\"price\":250.75,\"quantity\":10}"
    local product_response_2=$(curl -s -X POST "${BASE_URL}/api/products/" \
        -H "Content-Type: application/json" \
        -d "$product_data_2")
    echo "Ответ добавления второго товара: $product_response_2"
    local product_id_2=$(echo "$product_response_2" | grep -o '"id":"[^"]*' | sed 's/"id":"//;s/".*//')
    if [ -n "$product_id_2" ]; then
        echo -e "${GREEN}✓ Получен ID второго товара: $product_id_2${NC}"
    fi

    # 18. Получение списка всех товаров
    print_header "Получение списка всех товаров"
    local all_products_response=$(curl -s -X GET "${BASE_URL}/api/products/")
    echo "Список всех товаров: $all_products_response"

    # 19. Обновление данных товара
    print_header "Обновление данных товара"
    local update_product_data="{\"name\":\"Обновленный тестовый товар\",\"price\":150.00}"
    local update_product_response=$(curl -s -X PUT "${BASE_URL}/api/products/$product_id" \
        -H "Content-Type: application/json" \
        -d "$update_product_data")
    echo "Ответ обновления товара: $update_product_response"

    # 20. Удаление товара
    print_header "Удаление товара"
    local delete_product_response=$(curl -s -w "%{http_code}" -o /dev/null -X DELETE "${BASE_URL}/api/products/$product_id")
    if [ "$delete_product_response" -eq 204 ]; then
        echo -e "${GREEN}✓ Товар успешно удален (код: 204 No Content)${NC}"
        # Попытка получить удаленный товар
        local get_deleted_product_response=$(curl -s -w "%{http_code}" -o /dev/null "${BASE_URL}/api/products/$product_id")
        if [ "$get_deleted_product_response" -eq 404 ]; then
            echo -e "${GREEN}✓ Попытка получения удаленного товара корректно вернула 404 Not Found${NC}"
        else
            echo -e "${RED}✗ Попытка получения удаленного товара вернула код $get_deleted_product_response вместо 404${NC}"
        fi
    else
        echo -e "${RED}✗ Не удалось удалить товар (код: $delete_product_response)${NC}"
    fi

    # 21. Регистрация пользователя с уже существующим именем
    print_header "Регистрация пользователя с уже существующим именем"
    local register_duplicate_data="{\"username\":\"$username\",\"full_name\":\"Duplicate User\",\"phone\":\"+7 (999) 000-00-00\",\"password\":\"password123\"}"
    local register_duplicate_response=$(curl -s -X POST "${BASE_URL}/user-api/users/register" \
        -H "Content-Type: application/json" \
        -d "$register_duplicate_data")
    echo "Ответ регистрации дубликата: $register_duplicate_response"
    if [[ $(echo "$register_duplicate_response" | grep -c "Username already registered") -gt 0 ]]; then
        echo -e "${GREEN}✓ Сервер корректно обработал регистрацию дубликата пользователя${NC}"
    else
        echo -e "${RED}✗ Сервер некорректно обработал регистрацию дубликата пользователя${NC}"
    fi

    # 22. Попытка входа с неверным паролем
    print_header "Попытка входа с неверным паролем"
    local wrong_auth_data="username=$username&password=wrongpassword"
    local wrong_auth_response=$(curl -s -X POST "${BASE_URL}/user-api/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "$wrong_auth_data")
    echo "Ответ аутентификации с неверным паролем: $wrong_auth_response"
    if [[ $(echo "$wrong_auth_response" | grep -c "Incorrect username or password") -gt 0 ]]; then
        echo -e "${GREEN}✓ Сервер корректно обработал неверный пароль${NC}"
    else
        echo -e "${RED}✗ Сервер некорректно обработал неверный пароль${NC}"
    fi

    print_header "Все тесты завершены"
}

# Запуск главной функции
main 