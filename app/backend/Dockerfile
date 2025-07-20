# Файл: app/backend/Dockerfile

FROM python:3.11-slim
WORKDIR /app

# Путь к requirements.txt от корня проекта
COPY app/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Путь к исходникам от корня проекта
COPY app/backend/src ./src

EXPOSE 8000
CMD ["uvicorn", "src.__main__:app", "--host", "0.0.0.0", "--port", "8000"]