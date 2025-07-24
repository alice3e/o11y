import logging
import os
import time
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

log = logging.getLogger()
log.setLevel('INFO')
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
log.addHandler(handler)

# Импорт метрик (будет импортирован при инициализации)
metrics_collector = None

KEYSPACE = "store"


def get_cassandra_session():
    """Подключение к Cassandra и возвращение сессии."""
    global metrics_collector
    
    cassandra_host = os.environ.get("CASSANDRA_HOST", "127.0.0.1")
    cluster = Cluster([cassandra_host])
    
    start_time = time.time()
    session = cluster.connect()
    
    # Записываем метрики подключения
    if metrics_collector:
        duration = time.time() - start_time
        metrics_collector.record_db_query('connect', duration)

    rows = session.execute("SELECT keyspace_name FROM system_schema.keyspaces")
    if KEYSPACE in [row[0] for row in rows]:
        log.info(f"Keyspace '{KEYSPACE}' already exists.")
    else:
        log.info(f"Creating keyspace '{KEYSPACE}'...")
        session.execute(f"""
            CREATE KEYSPACE {KEYSPACE}
            WITH replication = {{ 'class': 'SimpleStrategy', 'replication_factor': '1' }}
        """)

    session.set_keyspace(KEYSPACE)
    return session


def create_schema(session):
    """Создание таблиц в Cassandra."""
    global metrics_collector
    
    # Drop the existing table to recreate with new schema
    try:
        log.info("Dropping table 'products' if exists...")
        start_time = time.time()
        session.execute("DROP TABLE IF EXISTS products")
        if metrics_collector:
            duration = time.time() - start_time
            metrics_collector.record_db_query('drop_table', duration)
        log.info("Table 'products' dropped.")
    except Exception as e:
        log.warning(f"Error dropping table: {e}")
    
    log.info("Creating table 'products'...")
    start_time = time.time()
    session.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id UUID PRIMARY KEY,
            name TEXT,
            category TEXT,
            price DECIMAL,
            quantity INT,
            description TEXT,
            manufacturer TEXT
        );
    """)
    if metrics_collector:
        duration = time.time() - start_time
        metrics_collector.record_db_query('create_table', duration)
    log.info("Table 'products' created.")


def init_cassandra():
    """Инициализация Cassandra: подключение, создание keyspace и таблиц."""
    global metrics_collector
    
    # Импортируем метрики только при инициализации, чтобы избежать циклических импортов
    try:
        from .metrics import metrics_collector as mc
        metrics_collector = mc
    except ImportError:
        log.warning("Metrics module not available")
    
    for i in range(10):  # 10 попыток подключения
        try:
            session = get_cassandra_session()
            create_schema(session)
            
            # Обновляем сессию в сборщике метрик
            if metrics_collector:
                metrics_collector.update_cassandra_session(session)
                # Обновляем метрики продуктов при инициализации
                metrics_collector.update_product_metrics()
            
            return session
        except Exception as e:
            log.error(f"Could not connect to Cassandra. Retrying in 10 seconds... ({e})")
            time.sleep(10)
    log.error("Failed to connect to Cassandra after several retries.")
    raise SystemExit("Failed to connect to Cassandra") 