#!/bin/sh
# entrypoint.sh

# Запускаем скрипт для генерации swagger.json
echo "Generating combined swagger.json..."
python /app/generate_swagger.py

# Проверяем, что файл успешно создан
if [ ! -f /usr/share/nginx/html/swagger.json ]; then
    echo "Failed to generate swagger.json. Exiting."
    exit 1
fi

echo "swagger.json generated successfully. Starting Nginx..."

# Запускаем Nginx в фоновом режиме
exec nginx -g 'daemon off;' 