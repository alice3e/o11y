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

KEYSPACE = "store"


def get_cassandra_session():
    """Подключение к Cassandra и возвращение сессии."""
    cassandra_host = os.environ.get("CASSANDRA_HOST", "127.0.0.1")
    cluster = Cluster([cassandra_host])
    session = cluster.connect()

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
    # Drop the existing table to recreate with new schema
    try:
        log.info("Dropping table 'products' if exists...")
        session.execute("DROP TABLE IF EXISTS products")
        log.info("Table 'products' dropped.")
    except Exception as e:
        log.warning(f"Error dropping table: {e}")
    
    log.info("Creating table 'products'...")
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
    log.info("Table 'products' created.")


def init_cassandra():
    """Инициализация Cassandra: подключение, создание keyspace и таблиц."""
    for i in range(10):  # 10 попыток подключения
        try:
            session = get_cassandra_session()
            create_schema(session)
            return session
        except Exception as e:
            log.error(f"Could not connect to Cassandra. Retrying in 10 seconds... ({e})")
            time.sleep(10)
    log.error("Failed to connect to Cassandra after several retries.")
    raise SystemExit("Failed to connect to Cassandra") 