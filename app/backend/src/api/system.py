# Файл: app/backend/src/api/system.py
import os
import time
from fastapi import APIRouter, Response, status
from cassandra.cluster import Cluster, NoHostAvailable

# Создаем новый "роутер". Его можно воспринимать как мини-приложение FastAPI.
router = APIRouter(
    prefix="/system",  # Все эндпоинты в этом файле будут начинаться с /system
    tags=["System"],   # Группируем их в Swagger под тегом "System"
)

CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "cassandra")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", 9042))


def get_metrics_collector():
    """Получить сборщик метрик"""
    try:
        from ..services.metrics import metrics_collector
        return metrics_collector
    except ImportError:
        return None

@router.get("/health", summary="Проверка состояния сервиса и подключения к БД")
def health_check(response: Response):
    """
    Проверяет доступность Cassandra.
    Возвращает 200 OK, если все хорошо.
    Возвращает 503 Service Unavailable, если БД недоступна.
    """
    metrics_collector = get_metrics_collector()
    
    try:
        cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
        
        query_start_time = time.time()
        session = cluster.connect()
        session.execute("SELECT release_version FROM system.local")
        
        if metrics_collector:
            query_duration = time.time() - query_start_time
            metrics_collector.record_db_query('health_check', query_duration)
        
        session.shutdown()
        cluster.shutdown()
        return {"status": "ok", "database_connection": "ok"}
    except NoHostAvailable:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "database_connection": "unavailable"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"status": "error", "database_connection": f"error: {e}"}