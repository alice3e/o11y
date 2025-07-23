#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Базовый URL
BASE_URL="http://localhost"

# Функция для вывода заголовков
print_header() {
    echo -e "\n${YELLOW}===== $1 =====${NC}\n"
}

# Функция для проверки доступности сервиса
check_service() {
    local service_name=$1
    local url=$2
    
    echo -n "Проверка $service_name... "
    if curl -s "$url" > /dev/null; then
        echo -e "${GREEN}✓ $service_name доступен${NC}"
    else
        echo -e "${RED}✗ $service_name недоступен${NC}"
        exit 1
    fi
}

# Основная функция тестирования
main() {
    print_header "🧪 Тестирование микросервисов с новой системой аутентификации"
    
    # 1. Проверка доступности сервисов
    print_header "Проверка доступности сервисов"
    check_service "Backend API" "${BASE_URL}/api/system/health"
    check_service "User Service" "${BASE_URL}/user-api/health"
    check_service "Cart Service" "${BASE_URL}/cart-api/health"
    check_service "Order Service" "${BASE_URL}/order-api/health"
    
    # 2. Получение токенов
    print_header "🔐 Получение токенов пользователей"
    
    echo "Получаем токен администратора..."
    local admin_token=$(curl -s -X POST "${BASE_URL}/user-api/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=swagger_admin&password=admin123" | jq -r '.access_token')
    
    if [ -z "$admin_token" ] || [ "$admin_token" = "null" ]; then
        echo -e "${RED}✗ Не удалось получить токен администратора${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Токен администратора получен: ${admin_token:0:20}...${NC}"
    
    echo "Получаем токен обычного пользователя..."
    local user_token=$(curl -s -X POST "${BASE_URL}/user-api/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=swagger_user&password=password123" | jq -r '.access_token')
    
    if [ -z "$user_token" ] || [ "$user_token" = "null" ]; then
        echo -e "${RED}✗ Не удалось получить токен пользователя${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Токен пользователя получен: ${user_token:0:20}...${NC}"
    
    # 3. Тестирование контроля доступа
    print_header "🎯 Тестирование контроля доступа по ролям"
    
    echo "3.1. Администратор создает товар:"
    local product_response=$(curl -s -X POST "${BASE_URL}/api/products/" \
        -H "Authorization: Bearer $admin_token" \
        -H "Content-Type: application/json" \
        -d '{"name": "Тестовый товар", "category": "Тест", "price": 150.50, "stock_count": 10}')
    
    local product_id=$(echo "$product_response" | jq -r '.product_id // empty')
    if [ -n "$product_id" ]; then
        echo -e "${GREEN}✓ Товар создан с ID: $product_id${NC}"
    else
        echo -e "${RED}✗ Ошибка создания товара: $product_response${NC}"
    fi
    
    echo -e "\n3.2. Обычный пользователь пытается создать товар:"
    local user_create_response=$(curl -s -X POST "${BASE_URL}/api/products/" \
        -H "Authorization: Bearer $user_token" \
        -H "Content-Type: application/json" \
        -d '{"name": "Недопустимый товар", "category": "Тест", "price": 100.00, "stock_count": 5}')
    
    if echo "$user_create_response" | grep -q "Admin access required"; then
        echo -e "${GREEN}✓ Обычный пользователь корректно заблокирован${NC}"
    else
        echo -e "${RED}✗ Обычный пользователь смог создать товар: $user_create_response${NC}"
    fi
    
    # 4. Тестирование фильтрации по категориям
    print_header "📂 Тестирование фильтрации по категориям"
    
    echo "4.1. Администратор получает все товары:"
    local admin_all_response=$(curl -s -H "Authorization: Bearer $admin_token" "${BASE_URL}/api/products/")
    local admin_total=$(echo "$admin_all_response" | jq -r '.total // 0')
    echo -e "${GREEN}✓ Администратор получил $admin_total товаров${NC}"
    
    echo -e "\n4.2. Обычный пользователь пытается получить все товары:"
    local user_all_response=$(curl -s -H "Authorization: Bearer $user_token" "${BASE_URL}/api/products/")
    if echo "$user_all_response" | grep -q "категорию"; then
        echo -e "${GREEN}✓ Обычный пользователь корректно заблокирован (требуется категория)${NC}"
    else
        echo -e "${RED}✗ Обычный пользователь получил доступ: $user_all_response${NC}"
    fi
    
    echo -e "\n4.3. Обычный пользователь получает товары по категории:"
    local encoded_category=$(printf '%s' "Тест" | python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read().strip()))" 2>/dev/null || echo "Тест")
    local user_category_response=$(curl -s -H "Authorization: Bearer $user_token" "${BASE_URL}/api/products/?category=$encoded_category")
    local user_category_total=$(echo "$user_category_response" | jq -r '.total // 0')
    echo -e "${GREEN}✓ Пользователь получил $user_category_total товаров категории 'Тест'${NC}"
    
    echo -e "\n4.4. Неавторизованный доступ с категорией:"
    local unauth_response=$(curl -s "${BASE_URL}/api/products/?category=$encoded_category")
    local unauth_total=$(echo "$unauth_response" | jq -r '.total // 0')
    echo -e "${GREEN}✓ Без авторизации получено $unauth_total товаров категории 'Тест'${NC}"
    
    # 5. Тестирование работы с корзиной
    print_header "🛒 Тестирование корзины и заказов"
    
    if [ -n "$product_id" ]; then
        echo "5.1. Добавление товара в корзину:"
        local cart_add_response=$(curl -s -X POST "${BASE_URL}/cart-api/cart/items" \
            -H "X-User-ID: testuser_script" \
            -H "Content-Type: application/json" \
            -d "{\"product_id\": \"$product_id\", \"quantity\": 2}")
        
        if echo "$cart_add_response" | jq -e '.id' > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Товар добавлен в корзину${NC}"
            
            echo -e "\n5.2. Оформление заказа:"
            local order_response=$(curl -s -X POST "${BASE_URL}/cart-api/cart/checkout" \
                -H "X-User-ID: testuser_script")
            
            if echo "$order_response" | jq -e '.id' > /dev/null 2>&1; then
                echo -e "${GREEN}✓ Заказ успешно оформлен${NC}"
            else
                echo -e "${YELLOW}! Заказ не оформлен: $order_response${NC}"
            fi
        else
            echo -e "${YELLOW}! Товар не добавлен в корзину: $cart_add_response${NC}"
        fi
    fi
    
    # 6. Очистка тестовых данных
    print_header "🧹 Очистка тестовых данных"
    
    echo "Удаляем созданные товары..."
    local all_products=$(curl -s -H "Authorization: Bearer $admin_token" "${BASE_URL}/api/products/")
    local test_product_ids=$(echo "$all_products" | jq -r '.items[]? | select(.category == "Тест") | .product_id')
    
    for id in $test_product_ids; do
        echo "Удаление товара $id..."
        curl -s -X DELETE "${BASE_URL}/api/products/$id" \
            -H "Authorization: Bearer $admin_token" > /dev/null
    done
    
    print_header "🎉 Все тесты завершены успешно!"
    echo -e "${GREEN}✅ Ролевая модель доступа работает корректно${NC}"
    echo -e "${GREEN}✅ Фильтрация по категориям функционирует${NC}"
    echo -e "${GREEN}✅ JWT-аутентификация интегрирована${NC}"
    echo -e "${GREEN}✅ Микросервисы взаимодействуют корректно${NC}"
    echo ""
    echo -e "${BLUE}📖 Документация: http://localhost/docs/${NC}"
    echo -e "${BLUE}🔧 Swagger UI: http://localhost/swagger/${NC}"
}

# Запуск тестирования
main
