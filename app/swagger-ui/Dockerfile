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

# Копируем необходимые файлы со сборочного этапа
COPY --from=builder /app/generate_swagger.py /app/generate_swagger.py
COPY --from=builder /app/entrypoint.sh /app/entrypoint.sh

# Копируем HTML-страницу и конфигурацию Nginx
COPY app/swagger-ui/index.html /usr/share/nginx/html/index.html
COPY app/swagger-ui/nginx.conf /etc/nginx/conf.d/default.conf

# Устанавливаем Python и зависимости, необходимые для entrypoint
RUN apk --no-cache add python3 py3-pip && \
    pip3 install --no-cache-dir requests && \
    ln -sf /usr/bin/python3 /usr/bin/python

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем entrypoint
ENTRYPOINT ["/app/entrypoint.sh"] 