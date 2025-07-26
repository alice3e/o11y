# Файл: app/backend/src/__main__.py

import uvicorn
import time
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

# ИЗМЕНЕННЫЙ ИМПОРТ: Импортируем роутеры из __init__.py пакета api
from .api import system_router, products_router

# Импортируем сервис для работы с БД
from .services import cassandra
from .services.metrics import setup_metrics, metrics_collector

# Импортируем модуль трейсинга
from .tracing import setup_tracing, get_tracer

# Импортируем профилирование
from .profiling import ensure_profiles_dir


class MetricsMiddleware:
    """Middleware для автоматического сбора HTTP метрик"""
    
    def __init__(self, app):
        self.app = app
        
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
            
        # Извлекаем информацию о запросе
        method = scope["method"]
        path = scope["path"]
        
        # Нормализуем путь для группировки метрик
        endpoint = self._normalize_endpoint(path)
        
        start_time = time.time()
        
        # Создаем обертку для отслеживания статус кода
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Записываем метрики после обработки запроса (исключая сам эндпоинт метрик)
            if endpoint and endpoint != "/metrics":
                duration = time.time() - start_time
                if metrics_collector:
                    metrics_collector.record_request(method, endpoint, status_code, duration)
    
    def _normalize_endpoint(self, path: str) -> str:
        """Нормализация пути для группировки метрик"""
        # Заменяем UUID и числовые ID на параметры
        import re
        
        # UUID паттерн
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{product_id}', path)
        
        # Числовые ID
        path = re.sub(r'/\d+', '/{id}', path)
        
        # Удаляем query параметры
        if '?' in path:
            path = path.split('?')[0]
            
        return path


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... (эта часть без изменений)
    print("Application startup: Connecting to database...")
    app.state.cassandra_session = cassandra.init_cassandra()
    print("Application startup: Database ready.")
    
    # Настраиваем метрики после инициализации БД
    setup_metrics(app, app.state.cassandra_session)
    print("Application startup: Metrics configured.")
    
    # Инициализируем профилирование
    profiling_enabled = os.getenv('ENABLE_PROFILING', 'false').lower() == 'true'
    if profiling_enabled:
        ensure_profiles_dir()
        print("Application startup: Profiling enabled and configured.")
    else:
        print("Application startup: Profiling disabled.")
    
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
    lifespan=lifespan
)

# Инициализация OpenTelemetry трейсинга
tracer = setup_tracing(app)
print("Tracing initialized for Backend Service")

# --- Добавляем middleware для метрик ---
app.add_middleware(MetricsMiddleware)

# --- Подключение роутеров ---
# ИСПОЛЬЗУЕМ НОВЫЕ ИМЕНА
app.include_router(system_router)
app.include_router(products_router)

# --- Эндпоинт для метрик ---
from fastapi import Response
from prometheus_client import generate_latest

@app.get("/metrics")
def metrics():
    """Эндпоинт для получения метрик Prometheus"""
    return Response(content=generate_latest(), media_type="text/plain")

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