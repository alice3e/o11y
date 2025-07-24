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
        # Use GET request instead of HEAD
        if wget -q -O /dev/null "$SERVICE_URL" 2>/dev/null; then
            echo "$SERVICE_NAME is available!"
            return 0
        fi
        
        retries=$((retries+1))
        echo "$SERVICE_NAME not available yet. Retry $retries/$MAX_RETRIES..."
        sleep $RETRY_DELAY
    done
    
    echo "Warning: $SERVICE_NAME did not become available in time, but continuing anyway..."
    return 0  # Continue even if service is not available
}

# Функция для проверки доступности OpenAPI спецификации
check_openapi() {
    SERVICE_URL=$1
    SERVICE_NAME=$2
    MAX_RETRIES=10
    RETRY_DELAY=3
    
    echo "Checking OpenAPI spec for $SERVICE_NAME at $SERVICE_URL..."
    
    retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        if wget -q -O - "$SERVICE_URL" 2>/dev/null | grep -q "openapi"; then
            echo "OpenAPI spec for $SERVICE_NAME is valid!"
            return 0
        fi
        
        retries=$((retries+1))
        echo "OpenAPI spec for $SERVICE_NAME not valid yet. Retry $retries/$MAX_RETRIES..."
        sleep $RETRY_DELAY
    done
    
    echo "Warning: OpenAPI spec for $SERVICE_NAME could not be validated, but continuing anyway..."
    return 0
}

# Create a minimal swagger.json to start with
echo "Creating initial minimal swagger.json..."
cat > /usr/share/nginx/html/swagger.json << EOF
{
  "openapi": "3.0.0",
  "info": {
    "title": "Temporary API Documentation",
    "description": "Services are still starting up. Please refresh the page in a few moments.",
    "version": "1.0.0"
  },
  "paths": {
    "/api/system/health": {
      "get": {
        "summary": "Check system health",
        "responses": {
          "200": {
            "description": "System is healthy"
          }
        }
      }
    }
  }
}
EOF

# Start Nginx in the background
echo "Starting Nginx with minimal swagger.json..."
nginx

# Ожидаем доступности всех микросервисов в фоновом режиме
(
    # Сначала проверяем базовую доступность сервисов
    wait_for_service "http://backend:8000/" "Backend API"
    wait_for_service "http://cart-service:8001/docs" "Cart Service"
    wait_for_service "http://order-service:8002/docs" "Order Service"
    wait_for_service "http://user-service:8003/docs" "User Service"
    
    # Затем проверяем доступность OpenAPI спецификаций
    check_openapi "http://backend:8000/openapi.json" "Backend API"
    check_openapi "http://cart-service:8001/openapi.json" "Cart Service"
    check_openapi "http://order-service:8002/openapi.json" "Order Service"
    check_openapi "http://user-service:8003/openapi.json" "User Service"
    
    # Запускаем скрипт для генерации swagger.json
    echo "All services checked! Generating combined swagger.json..."
    python3 /app/generate_swagger.py
    
    # Проверяем, что файл успешно создан
    if [ ! -f /usr/share/nginx/html/swagger.json ]; then
        echo "Failed to generate swagger.json. Keeping minimal version..."
    else
        echo "swagger.json generated successfully!"
    fi
    
    # Периодически пытаемся обновить swagger.json
    while true; do
        echo "Will attempt to regenerate swagger.json in 60 seconds..."
        sleep 60
        echo "Regenerating swagger.json..."
        python3 /app/generate_swagger.py
    done
) &

# Держим контейнер запущенным
echo "Swagger UI is ready at http://localhost/swagger/"
tail -f /dev/null 