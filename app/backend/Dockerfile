# Используем slim-образ Python как основу
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем сначала файл с зависимостями, чтобы использовать кеширование Docker
COPY requirements.txt .

# Устанавливаем зависимости. --no-cache-dir уменьшает размер образа.
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь исходный код нашего приложения
COPY ./src ./src

# Информируем Docker, что контейнер будет слушать на порту 8000
EXPOSE 8000

# Команда для запуска приложения. Uvicorn будет доступен в $PATH.
CMD ["uvicorn", "src.__main__:app", "--host", "0.0.0.0", "--port", "8000"]