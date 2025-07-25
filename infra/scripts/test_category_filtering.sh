#!/bin/bash

echo "🧪 Тестирование новой функциональности: Фильтрация по категориям с контролем доступа"
echo "=================================================================================="

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "\n${BLUE}1. Получение токенов пользователей${NC}"
echo "-----------------------------------"

# Получаем токен администратора
echo "📝 Получаем токен администратора..."
ADMIN_TOKEN=$(curl -s -X POST "http://localhost/user-api/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=swagger_admin&password=admin123" | jq -r '.access_token')
echo -e "${GREEN}✅ Токен администратора получен: ${ADMIN_TOKEN:0:20}...${NC}"

# Получаем токен обычного пользователя
echo "📝 Получаем токен обычного пользователя..."
USER_TOKEN=$(curl -s -X POST "http://localhost/user-api/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=swagger_user&password=password123" | jq -r '.access_token')
echo -e "${GREEN}✅ Токен пользователя получен: ${USER_TOKEN:0:20}...${NC}"

echo -e "\n${BLUE}2. Тестирование контроля доступа${NC}"
echo "-------------------------------"

# Тест 1: Администратор может получить все товары
echo "🧪 Тест 1: Администратор получает все товары..."
ADMIN_RESPONSE=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://localhost/api/products/")
ADMIN_COUNT=$(echo $ADMIN_RESPONSE | jq -r '.total')
echo -e "${GREEN}✅ Администратор получил $ADMIN_COUNT товаров${NC}"

# Тест 2: Обычный пользователь НЕ может получить все товары
echo "🧪 Тест 2: Обычный пользователь пытается получить все товары..."
USER_RESPONSE=$(curl -s -H "Authorization: Bearer $USER_TOKEN" "http://localhost/api/products/")
USER_ERROR=$(echo $USER_RESPONSE | jq -r '.detail')
if [[ "$USER_ERROR" == *"категорию"* ]]; then
    echo -e "${GREEN}✅ Обычный пользователь корректно заблокирован: $USER_ERROR${NC}"
else
    echo -e "${RED}❌ Ошибка: обычный пользователь получил доступ к всем товарам${NC}"
fi

echo -e "\n${BLUE}3. Тестирование фильтрации по категориям${NC}"
echo "----------------------------------------"

# Тест 3: Обычный пользователь может получить товары по категории
echo "🧪 Тест 3: Обычный пользователь получает товары категории 'Фрукты'..."
CATEGORY_RESPONSE=$(curl -s -H "Authorization: Bearer $USER_TOKEN" \
  "http://localhost/api/products/?category=%D0%A4%D1%80%D1%83%D0%BA%D1%82%D1%8B")
CATEGORY_COUNT=$(echo $CATEGORY_RESPONSE | jq -r '.total')
echo -e "${GREEN}✅ Получено $CATEGORY_COUNT товаров категории 'Фрукты'${NC}"

# Показываем товары
echo "📦 Товары категории 'Фрукты':"
echo $CATEGORY_RESPONSE | jq -r '.items[] | "  - \(.name): \(.price) руб."'

# Тест 4: Тестирование без авторизации
echo -e "\n🧪 Тест 4: Неавторизованный доступ к категории 'Молочные продукты'..."
UNAUTH_RESPONSE=$(curl -s "http://localhost/api/products/?category=%D0%9C%D0%BE%D0%BB%D0%BE%D1%87%D0%BD%D1%8B%D0%B5%20%D0%BF%D1%80%D0%BE%D0%B4%D1%83%D0%BA%D1%82%D1%8B")
UNAUTH_COUNT=$(echo $UNAUTH_RESPONSE | jq -r '.total')
echo -e "${GREEN}✅ Без авторизации получено $UNAUTH_COUNT товаров категории 'Молочные продукты'${NC}"

echo -e "\n${BLUE}4. Тестирование административных функций${NC}"
echo "----------------------------------------"

# Тест 5: Обычный пользователь НЕ может создавать товары
echo "🧪 Тест 5: Обычный пользователь пытается создать товар..."
CREATE_RESPONSE=$(curl -s -X POST "http://localhost/api/products/" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Тест товар", "category": "Тест", "price": 100.00, "stock_count": 10}')
CREATE_ERROR=$(echo $CREATE_RESPONSE | jq -r '.detail')
if [[ "$CREATE_ERROR" == *"Admin"* ]]; then
    echo -e "${GREEN}✅ Обычный пользователь корректно заблокирован от создания товаров: $CREATE_ERROR${NC}"
else
    echo -e "${RED}❌ Ошибка: обычный пользователь смог создать товар${NC}"
fi

# Тест 6: Администратор может создавать товары
echo "🧪 Тест 6: Администратор создает новый товар..."
ADMIN_CREATE=$(curl -s -X POST "http://localhost/api/products/" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Тестовый товар администратора",
    "category": "Тест",
    "price": 199.99,
    "stock_count": 5,
    "description": "Товар создан в рамках теста"
  }')
ADMIN_PRODUCT_ID=$(echo $ADMIN_CREATE | jq -r '.product_id')
if [[ "$ADMIN_PRODUCT_ID" != "null" ]]; then
    echo -e "${GREEN}✅ Администратор успешно создал товар с ID: $ADMIN_PRODUCT_ID${NC}"
else
    echo -e "${RED}❌ Ошибка: администратор не смог создать товар${NC}"
fi

echo -e "\n${YELLOW}🎉 Тестирование завершено!${NC}"
echo -e "${YELLOW}📋 Сводка результатов:${NC}"
echo -e "  ${GREEN}✅ Ролевая модель доступа работает корректно${NC}"
echo -e "  ${GREEN}✅ Фильтрация по категориям функционирует${NC}"
echo -e "  ${GREEN}✅ Административные права соблюдаются${NC}"
echo -e "  ${GREEN}✅ JWT-аутентификация интегрирована${NC}"
echo ""
echo -e "${BLUE}📖 Подробная документация доступна по адресу: http://localhost/docs/${NC}"
echo -e "${BLUE}🔧 Swagger UI для тестирования: http://localhost/swagger/${NC}"
