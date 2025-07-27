import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_fastapi_instrumentator import Instrumentator


# Счетчики запросов
request_count = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# Время выполнения запросов
request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

# Метрики базы данных
db_connection_count = Gauge(
    'cassandra_connections_active',
    'Number of active Cassandra connections'
)

db_query_count = Counter(
    'cassandra_queries_total',
    'Total number of Cassandra queries',
    ['operation']
)

db_query_duration = Histogram(
    'cassandra_query_duration_seconds',
    'Cassandra query execution time',
    ['operation']
)

# Метрики продуктов
products_total = Gauge(
    'products_total',
    'Total number of products in the database'
)

products_by_category = Gauge(
    'products_by_category',
    'Number of products by category',
    ['category']
)


class MetricsCollector:
    """Класс для сбора и обновления метрик"""
    
    def __init__(self, cassandra_session=None):
        self.cassandra_session = cassandra_session
        
    def update_cassandra_session(self, session):
        """Обновить сессию Cassandra"""
        self.cassandra_session = session
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Записать метрики HTTP запроса"""
        request_count.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        request_duration.labels(method=method, endpoint=endpoint).observe(duration)
    
    def record_db_query(self, operation: str, duration: float):
        """Записать метрики запроса к БД"""
        db_query_count.labels(operation=operation).inc()
        db_query_duration.labels(operation=operation).observe(duration)
    
    def update_product_metrics(self):
        """Обновить метрики продуктов
        
        Этот метод вызывается только при health check для снижения нагрузки на БД.
        Ранее вызывался при каждом добавлении/изменении/удалении товара.
        
        ВРЕМЕННО ОТКЛЮЧЕНО: полное сканирование таблицы products создает слишком 
        большую нагрузку на Cassandra из-за tombstone-ячеек.
        """
        if not self.cassandra_session:
            return
            
        try:
            start_time = time.time()
            
            # ВРЕМЕННО ОТКЛЮЧЕНО: COUNT(*) и SELECT category сканируют всю таблицу
            # и создают огромную нагрузку при наличии большого количества tombstone-ячеек
            
            # Простая проверка доступности таблицы вместо полного сканирования
            result = self.cassandra_session.execute("SELECT id FROM products LIMIT 1")
            
            # Устанавливаем фиксированные значения или пропускаем обновление метрик
            # products_total.set(0)  # Отключено
            # products_by_category.labels(category="unknown").set(0)  # Отключено
            
            duration = time.time() - start_time
            self.record_db_query('product_metrics_update', duration)
            
        except Exception as e:
            print(f"Error updating product metrics: {e}")


# Глобальный экземпляр сборщика метрик
metrics_collector = MetricsCollector()


def setup_metrics(app, cassandra_session=None):
    """Настройка метрик для FastAPI приложения"""
    
    # Обновляем сессию в сборщике метрик
    if cassandra_session:
        metrics_collector.update_cassandra_session(cassandra_session)
    
    # Простое логирование что метрики настроены
    print("Metrics collector configured with Cassandra session")
    
    return None


def get_metrics():
    """Получить метрики в формате Prometheus"""
    return generate_latest()
