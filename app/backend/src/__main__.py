# Файл: app/backend/src/__main__.py

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI

# ИЗМЕНЕННЫЙ ИМПОРТ: Импортируем роутеры из __init__.py пакета api
from .api import system_router, products_router

# Импортируем сервис для работы с БД
from .services import cassandra
from .services.metrics import setup_metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... (эта часть без изменений)
    print("Application startup: Connecting to database...")
    app.state.cassandra_session = cassandra.init_cassandra()
    print("Application startup: Database ready.")
    
    # Настраиваем метрики после инициализации БД
    setup_metrics(app, app.state.cassandra_session)
    print("Application startup: Metrics configured.")
    
    yield
    print("Application shutdown: Closing database connection...")
    app.state.cassandra_session.shutdown()
    print("Application shutdown: Complete.")


# Создаем основной экземпляр приложения
app = FastAPI(
    title="Product Store API",
    description="Бэкенд-сервис для ДЗ по Observability",
    version="0.1.0",
    docs_url="/swagger",
    redoc_url=None,
    openapi_url="/openapi.json",
    root_path="/api",
    lifespan=lifespan
)

# --- Подключение роутеров ---
# ИСПОЛЬЗУЕМ НОВЫЕ ИМЕНА
app.include_router(system_router)
app.include_router(products_router)

# --- Эндпоинт для метрик ---
from fastapi import Response
from .services.metrics import get_metrics

@app.get("/metrics")
def metrics():
    """Эндпоинт для получения метрик Prometheus"""
    return Response(content=get_metrics(), media_type="text/plain")

# --- Корневой эндпоинт API ---
@app.get("/")
def api_root():
    """Корневой эндпоинт API, доступный по /api/"""
    return {"message": "Welcome to the Product Store API"}

# --- Точка входа для запуска через uvicorn ---
if __name__ == "__main__":
    uvicorn.run(
        "__main__:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )