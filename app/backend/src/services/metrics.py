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
        """Обновить метрики продуктов"""
        if not self.cassandra_session:
            return
            
        try:
            start_time = time.time()
            
            # Общее количество продуктов
            result = self.cassandra_session.execute("SELECT COUNT(*) FROM products")
            total_count = result.one()[0]
            products_total.set(total_count)
            
            # Количество продуктов по категориям
            # Поскольку GROUP BY не работает с category, получим все продукты и посчитаем вручную
            result = self.cassandra_session.execute("SELECT category FROM products")
            category_counts = {}
            
            for row in result:
                category = row.category or 'unknown'
                category_counts[category] = category_counts.get(category, 0) + 1
            
            # Обнуляем старые метрики категорий
            # (Prometheus будет автоматически убирать метрики, которые не обновляются)
            
            # Устанавливаем новые значения
            for category, count in category_counts.items():
                products_by_category.labels(category=category).set(count)
            
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
