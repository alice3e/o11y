#!/bin/sh
# entrypoint.sh

# Функция ожидания доступности сервиса
wait_for_service() {
    SERVICE_URL=$1
    SERVICE_NAME=$2
    MAX_RETRIES=30
    RETRY_DELAY=5
    
    echo "Waiting for $SERVICE_NAME to become available at $SERVICE_URL..."
    
    retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        if wget --spider -q "$SERVICE_URL"; then
            echo "$SERVICE_NAME is available!"
            return 0
        fi
        
        retries=$((retries+1))
        echo "$SERVICE_NAME not available yet. Retry $retries/$MAX_RETRIES..."
        sleep $RETRY_DELAY
    done
    
    echo "Error: $SERVICE_NAME did not become available in time"
    return 1
}

# Ожидаем доступности всех микросервисов
echo "Waiting for all services to become available..."

wait_for_service "http://backend:8000/openapi.json" "Backend API"
wait_for_service "http://cart-service:8001/openapi.json" "Cart Service"
wait_for_service "http://order-service:8002/openapi.json" "Order Service"
wait_for_service "http://user-service:8003/openapi.json" "User Service"

# Запускаем скрипт для генерации swagger.json
echo "All services available! Generating combined swagger.json..."
python3 /app/generate_swagger.py

# Проверяем, что файл успешно создан
if [ ! -f /usr/share/nginx/html/swagger.json ]; then
    echo "Failed to generate swagger.json. Exiting."
    exit 1
fi

echo "swagger.json generated successfully. Starting Nginx..."

# Запускаем Nginx в фоновом режиме
exec nginx -g 'daemon off;' 