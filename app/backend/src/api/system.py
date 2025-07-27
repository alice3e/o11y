# Файл: app/backend/src/api/system.py
import os
import time
from fastapi import APIRouter, Response, status
from cassandra.cluster import Cluster, NoHostAvailable
from ..tracing import get_tracer
from ..profiling import profile_endpoint, list_available_profiles, ensure_profiles_dir

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
@profile_endpoint("health_check")
async def health_check(response: Response):
    """
    Проверяет доступность Cassandra.
    Возвращает 200 OK, если все хорошо.
    Возвращает 503 Service Unavailable, если БД недоступна.
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span("health_check") as span:
        span.set_attribute("check.type", "database_connection")
        span.set_attribute("db.host", CASSANDRA_HOST)
        span.set_attribute("db.port", CASSANDRA_PORT)
        
        metrics_collector = get_metrics_collector()
        
        try:
            with tracer.start_as_current_span("cassandra_connection") as db_span:
                db_span.set_attribute("db.operation", "connect")
                db_span.set_attribute("db.system", "cassandra")
                
                cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
                
                query_start_time = time.time()
                session = cluster.connect()
                session.execute("SELECT release_version FROM system.local")
                
                if metrics_collector:
                    query_duration = time.time() - query_start_time
                    metrics_collector.record_db_query('health_check', query_duration)
                    db_span.set_attribute("db.duration_seconds", query_duration)
                    
                    # Обновляем метрики продуктов при health check
                    metrics_collector.update_cassandra_session(session)
                    metrics_collector.update_product_metrics()
                
                session.shutdown()
                cluster.shutdown()
                
                span.set_attribute("health.status", "ok")
                span.set_attribute("db.status", "ok")
                return {"status": "ok", "database_connection": "ok"}
                
        except NoHostAvailable as e:
            span.set_attribute("health.status", "error")
            span.set_attribute("db.status", "unavailable")
            span.set_attribute("error.type", "NoHostAvailable")
            span.set_attribute("error.message", str(e))
            
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "error", "database_connection": "unavailable"}
            
        except Exception as e:
            span.set_attribute("health.status", "error")
            span.set_attribute("error.type", "UnexpectedError")
            span.set_attribute("error.message", str(e))
            
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {"status": "error", "database_connection": f"error: {e}"}


# Endpoints для управления профилированием
@router.get("/profiling/status")
@profile_endpoint("profiling_status")
async def get_profiling_status():
    """Получить статус профилирования"""
    ensure_profiles_dir()
    profiling_enabled = os.getenv('ENABLE_PROFILING', 'false').lower() == 'true'
    return {
        "profiling_enabled": profiling_enabled,
        "profiles_directory": "/app/profiles",
        "service": "backend"
    }


@router.get("/profiling/profiles")
@profile_endpoint("list_profiles")
async def get_available_profiles():
    """Получить список доступных профилей"""
    ensure_profiles_dir()
    profiles = list_available_profiles()
    return {
        "service": "backend",
        "available_profiles": profiles,
        "total_count": len(profiles)
    }