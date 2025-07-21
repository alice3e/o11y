# --- Сборочный этап ---
FROM python:3.9-slim as builder

# Устанавливаем зависимости
RUN pip install requests

# Копируем скрипт и entrypoint
COPY app/swagger-ui/generate_swagger.py /app/generate_swagger.py
COPY app/swagger-ui/entrypoint.sh /app/entrypoint.sh

# Даем права на выполнение entrypoint
RUN chmod +x /app/entrypoint.sh

# --- Финальный этап ---
FROM nginx:1.21-alpine

# Устанавливаем необходимые пакеты
RUN apk --no-cache add python3 py3-pip wget curl

# Устанавливаем Python зависимости
RUN pip3 install --no-cache-dir requests

# Копируем необходимые файлы со сборочного этапа
COPY --from=builder /app/generate_swagger.py /app/generate_swagger.py
COPY --from=builder /app/entrypoint.sh /app/entrypoint.sh

# Копируем HTML-страницу и конфигурацию Nginx
COPY app/swagger-ui/index.html /usr/share/nginx/html/index.html
COPY app/swagger-ui/nginx.conf /etc/nginx/conf.d/default.conf

# Определяем точку входа
ENTRYPOINT ["/app/entrypoint.sh"] 