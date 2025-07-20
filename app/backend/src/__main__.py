# Содержимое файла: app/backend/src/__main__.py
import os
import uvicorn
from fastapi import FastAPI, Response, status

# ИСПРАВЛЕННЫЙ ИМПОРТ
from cassandra.cluster import Cluster, NoHostAvailable
from cassandra.auth import PlainTextAuthProvider

# --- Настройки ---
CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "cassandra")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", 9042))


# --- Создание экземпляра приложения ---
app = FastAPI(
    title="Product Store",
    description="Система для домашнего задания по o11y",
    version="0.1.0",
)


# --- API Эндпоинты ---
@app.get("/")
async def root():
    """Простой эндпоинт для проверки, что сервис жив."""
    return {"message": "Product Store Service is running"}


@app.get("/health", summary="Проверка состояния сервиса и подключения к БД")
def health_check(response: Response):
    """
    Проверяет доступность Cassandra.
    Возвращает 200 OK, если все хорошо.
    Возвращает 503 Service Unavailable, если БД недоступна.
    """
    try:
        # Пытаемся установить соединение с Cassandra
        cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
        session = cluster.connect()
        session.execute("SELECT release_version FROM system.local")
        session.shutdown()
        cluster.shutdown()
        return {"status": "ok", "database_connection": "ok"}
    except NoHostAvailable:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "database_connection": "unavailable"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"status": "error", "database_connection": f"error: {e}"}


# --- Точка входа для запуска через uvicorn ---
if __name__ == "__main__":
    uvicorn.run(
        "__main__:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )