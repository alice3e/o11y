# infra/nginx/Dockerfile
FROM nginx:1.25-alpine

# Копируем наш кастомный конфиг, заменяя дефолтный
COPY nginx.conf /etc/nginx/conf.d/default.conf  