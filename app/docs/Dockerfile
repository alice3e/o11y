# Файл: app/docs/Dockerfile

FROM python:3.11-slim as builder

RUN pip install mkdocs mkdocs-material
WORKDIR /app

# Этот путь не меняется, так как он относится к исходникам
COPY app/docs-src ./docs

COPY app/docs/mkdocs.yml .

RUN mkdocs build

# --- Этап 2: Подача статики ---
FROM nginx:1.25-alpine
COPY --from=builder /app/site /usr/share/nginx/html