#!/bin/bash

# ==============================================================================
# Скрипт для массового создания товаров в Product Store API
#
# Описание:
# 1. Создает 50 пользователей-администраторов.
# 2. Получает для каждого из них JWT-токен.
# 3. В 50 параллельных потоках создает 5000 товаров (по 100 на каждого админа).
#
# ==============================================================================

set -e # Прекратить выполнение при любой ошибке

# --- КОНФИГУРАЦИЯ ---
readonly API_URL="http://localhost"
readonly NUM_ADMINS=10
readonly TARGET_PRODUCTS=5000
readonly PRODUCTS_PER_ADMIN=$((TARGET_PRODUCTS / NUM_ADMINS))

# --- ДАННЫЕ ДЛЯ ГЕНЕРАЦИИ ---
readonly CATEGORIES="Фрукты Овощи Молочные_продукты Напитки Бакалея Мясо Сладкое Пельмени Средства_для_уборки Сигареты Алкоголь"

# Функция для получения названий продуктов по категории (замена ассоциативного массива)
get_product_names_for_category() {
    case "$1" in
        "Фрукты") echo "Яблоки Бананы Апельсины Груши Киви" ;;
        "Овощи") echo "Морковь Картофель Лук Томаты Огурцы" ;;
        "Молочные_продукты") echo "Молоко Творог Сыр Йогурт Кефир" ;;
        "Напитки") echo "Кока-кола Спрайт Фанта Вода Сок" ;;
        "Бакалея") echo "Хлеб Макароны Рис Гречка Мука" ;;
        "Мясо") echo "Говядина Свинина Курица Индейка Колбаса" ;;
        "Сладкое") echo "Шоколад Конфеты Печенье Торт Мороженое" ;;
        "Пельмени") echo "Пельмени_мясные Вареники Манты Хинкали" ;;
        "Средства_для_уборки") echo "Порошок Мыло Шампунь Моющее_средство" ;;
        "Сигареты") echo "Marlboro Parliament Lucky_Strike Camel" ;;
        "Алкоголь") echo "Водка Вино Пиво Коньяк Виски" ;;
        *) echo "Generic_Product" ;;
    esac
}

# --- ЦВЕТА для вывода ---
readonly C_RESET='\033[0m'
readonly C_RED='\033[0;31m'
readonly C_GREEN='\033[0;32m'
readonly C_YELLOW='\033[0;33m'
readonly C_BLUE='\033[0;34m'
readonly C_CYAN='\033[0;36m'


# --- ФУНКЦИИ ---

register_admin() {
    local username=$1
    local password=$2
    local phone="+7$(($RANDOM % 900 + 100))$(($RANDOM % 9000 + 1000))$(($RANDOM % 9000 + 1000))"
    
    local payload
    payload=$(cat <<EOF
{
    "username": "$username",
    "full_name": "Seeder Admin $username",
    "phone": "$phone",
    "password": "$password"
}
EOF
)
    
    curl -s -X POST "${API_URL}/user-api/users/register" \
      -H "Content-Type: application/json" \
      -d "$payload" > /dev/null
}

login_and_get_token() {
    local username=$1
    local password=$2
    
    local token
    token=$(curl -s -X POST "${API_URL}/user-api/token" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=$username&password=$password" | jq -r '.access_token')
      
    if [ -z "$token" ] || [ "$token" = "null" ]; then
        echo "${C_RED}Ошибка: не удалось получить токен для пользователя $username${C_RESET}" >&2
        return 1
    fi
    
    echo "$token"
}

create_products_batch() {
    local worker_id=$1
    local token=$2
    local num_products=$3

    echo "${C_BLUE}Воркер #$worker_id (PID: $$) начал создание $num_products товаров...${C_RESET}"
    
    for i in $(seq 1 $num_products); do
        # Выбираем случайную категорию
        read -r -a categories_array <<< "$CATEGORIES"
        local category=${categories_array[$(($RANDOM % ${#categories_array[@]}))]}
        local category_name=$(echo "$category" | tr '_' ' ') # Заменяем подчеркивания на пробелы
        
        # Выбираем случайное название из этой категории
        local name_list
        name_list=$(get_product_names_for_category "$category")
        read -r -a names_array <<< "$name_list"
        local base_name=${names_array[$(($RANDOM % ${#names_array[@]}))]}
        local product_name="$(echo "$base_name" | tr '_' ' ') $RANDOM"
        
        # Генерируем случайную цену и количество
        local price
        price=$(printf "%.2f" "$(echo "scale=2; $RANDOM/327.67 * 10 + 10" | bc)")
        local stock=$(($RANDOM % 500 + 5000))
        
        local payload
        payload=$(cat <<EOF
{
    "name": "$product_name",
    "category": "$category_name",
    "price": $price,
    "stock_count": $stock
}
EOF
)
        curl -s -o /dev/null -X POST "${API_URL}/api/products/" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $token" \
            -d "$payload"
            
        if [ $((i % 20)) -eq 0 ]; then
            printf "${C_CYAN}.${C_RESET}"
        fi
    done
    
    echo "\n${C_GREEN}Воркер #$worker_id завершил работу.${C_RESET}"
}


# --- ОСНОВНАЯ ЛОГИКА СКРИПТА ---

echo "${C_YELLOW}--- Фаза 1: Регистрация и аутентификация $NUM_ADMINS администраторов ---${C_RESET}"

# Используем временный файл для хранения токенов, так как массивы в sh ограничены
TOKEN_FILE=$(mktemp)
trap 'rm -f -- "$TOKEN_FILE"' EXIT # Удаляем файл при выходе

for i in $(seq 1 $NUM_ADMINS); do
    ADMIN_USER="admin_$(date +%s)_${RANDOM}"
    ADMIN_PASS="seeder_password_123"
    
    printf "Создание админа #%s (%s)... " "$i" "$ADMIN_USER"
    
    register_admin "$ADMIN_USER" "$ADMIN_PASS"
    TOKEN=$(login_and_get_token "$ADMIN_USER" "$ADMIN_PASS")
    
    if [ $? -eq 0 ]; then
        echo "$TOKEN" >> "$TOKEN_FILE"
        echo "${C_GREEN}Успешно!${C_RESET}"
    else
        echo "${C_RED}Ошибка!${C_RESET}"
        exit 1
    fi
done

echo "\n${C_GREEN}Все $NUM_ADMINS администраторов успешно созданы и аутентифицированы.${C_RESET}"
echo "${C_YELLOW}--- Фаза 2: Параллельное создание $TARGET_PRODUCTS товаров ---${C_RESET}"
echo "Запускаем $NUM_ADMINS воркеров, каждый создает по $PRODUCTS_PER_ADMIN товаров."

worker_count=1
while read -r admin_token; do
    create_products_batch "$worker_count" "$admin_token" "$PRODUCTS_PER_ADMIN" &
    worker_count=$((worker_count + 1))
done < "$TOKEN_FILE"

echo "\n${C_BLUE}Все воркеры запущены. Ожидание завершения... (это может занять несколько минут)${C_RESET}"
wait

echo "\n${C_GREEN}=====================================================${C_RESET}"
echo "${C_GREEN}✅ Все задачи выполнены! $TARGET_PRODUCTS товаров создано.${C_RESET}"
echo "${C_GREEN}=====================================================${C_RESET}"