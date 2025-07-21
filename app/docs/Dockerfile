# Файл: app/docs/Dockerfile

FROM python:3.11-slim as builder

# Установка зависимостей
RUN pip install mkdocs mkdocs-material mkdocs-minify-plugin

# Настройка рабочей директории
WORKDIR /app

# Копирование исходных файлов документации
COPY app/docs-src ./docs
COPY app/docs/mkdocs.yml .

# Сборка документации
RUN mkdocs build

# Финальный образ
FROM nginx:1.25-alpine

# Копирование собранной документации
COPY --from=builder /app/site /usr/share/nginx/html

# Настройка Nginx
COPY app/docs/nginx.conf /etc/nginx/conf.d/default.conf

# Экспорт порта
EXPOSE 8000

# Запуск Nginx
CMD ["nginx", "-g", "daemon off;"]