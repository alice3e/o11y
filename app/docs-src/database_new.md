# 🗄️ База данных Product Store

Детальная документация по Apache Cassandra как основе для хранения данных с настройкой для высокой производительности и масштабируемости.

## 🏗️ Архитектура данных

### 📊 Обзор системы
- **СУБД**: Apache Cassandra 4.1 (NoSQL, column-family)
- **Keyspace**: `store` с SimpleStrategy репликацией
- **Replication Factor**: 1 (development), 3+ (production)
- **Consistency Level**: ONE (для dev), QUORUM (для prod)
- **Мониторинг**: MCAC Agent + Prometheus integration
- **Deployment**: Docker container с health checks

### 🎯 Принципы дизайна

#### **💡 NoSQL Advantages**
- **📈 Горизонтальное масштабирование**: Linear scalability с добавлением nodes
- **⚡ Высокая производительность**: O(1) reads по partition key
- **🔄 Partition Tolerance**: CAP theorem - consistency/availability trade-off
- **📊 Schema Flexibility**: Добавление полей без downtime
- **🚀 Write Optimization**: Append-only структура для быстрых записей

#### **🏗️ Data Modeling Strategy**
```cql
-- Основной принцип: Query-driven design
-- 1. Identify queries first
-- 2. Design tables around query patterns
-- 3. Minimize partitions per query
-- 4. Optimize for read performance
```

#### **🔑 Partitioning Strategy**
```python
# UUID partition key для равномерного распределения
# Избегаем hotspots и unbalanced clusters
partition_key = UUID()  # Random distribution
clustering_key = None   # Single-row partitions for products

# Преимущества UUID partitioning:
# ✅ Равномерное распределение нагрузки
# ✅ Отсутствие sequential hotspots
# ✅ Scalability без repartitioning
```

---

## 📋 Схема данных

### 🏪 Таблица: products

**Основная таблица для хранения каталога товаров магазина**

```cql
-- Keyspace definition
CREATE KEYSPACE IF NOT EXISTS store
WITH replication = {
    'class': 'SimpleStrategy',
    'replication_factor': 1
} AND durable_writes = true;

USE store;

-- Main products table
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY,                -- Partition key для равномерного распределения
    name TEXT,                          -- Название товара
    category TEXT,                      -- Категория (индексируется)
    price DECIMAL,                      -- Цена в рублях (индексируется)  
    quantity INT,                       -- Остаток на складе
    description TEXT,                   -- Подробное описание товара
    manufacturer TEXT,                  -- Производитель/бренд
    created_at TIMESTAMP,               -- Время создания записи
    updated_at TIMESTAMP                -- Время последнего обновления
) WITH gc_grace_seconds = 3600          -- Оптимизация для dev среды
AND compaction = {
    'class': 'SizeTieredCompactionStrategy',
    'max_threshold': 32,
    'min_threshold': 4
} AND compression = {
    'chunk_length_in_kb': 64,
    'class': 'LZ4Compressor'
} AND crc_check_chance = 1.0;
```

#### 📝 Структура полей

| Поле | Тип | Ключ | Nullable | Описание | Пример |
|------|-----|------|----------|----------|--------|
| `id` | UUID | 🔑 PRIMARY | ❌ | Уникальный идентификатор товара | `f767c2cb-215d-469e-a3be-c6e40a6cf47f` |
| `name` | TEXT | | ✅ | Название товара | `"Apple iPhone 14 Pro"` |
| `category` | TEXT | 📋 INDEX | ✅ | Категория товара | `"Electronics"` |
| `price` | DECIMAL | 📋 INDEX | ✅ | Цена товара в рублях | `99999.99` |
| `quantity` | INT | | ✅ | Количество на складе | `150` |
| `description` | TEXT | | ✅ | Подробное описание | `"Флагманский смартфон Apple"` |
| `manufacturer` | TEXT | | ✅ | Производитель/бренд | `"Apple Inc."` |
| `created_at` | TIMESTAMP | | ✅ | Время создания записи | `2024-01-15 10:30:00` |
| `updated_at` | TIMESTAMP | | ✅ | Время последнего обновления | `2024-01-16 14:45:00` |

---

## 🔍 Индексы и оптимизация

### 📊 Secondary Indexes

#### **🏷️ Category Index**
```cql
-- Индекс по категориям для фильтрации товаров
CREATE INDEX IF NOT EXISTS products_category_idx 
ON products (category);

-- Query examples:
SELECT * FROM products WHERE category = 'Electronics';
SELECT * FROM products WHERE category = 'Books' LIMIT 20;
```

**📈 Performance характеристики:**
- **Latency**: < 10ms для категории с 1000+ товарами
- **Throughput**: 500+ RPS per node
- **Memory Usage**: 2-5MB per category в индексе
- **Update Overhead**: 10-15% дополнительной записи

#### **💰 Price Index**
```cql
-- Индекс по цене для сортировки и фильтрации
CREATE INDEX IF NOT EXISTS products_price_idx 
ON products (price);

-- Query examples:
SELECT * FROM products WHERE price > 1000.00;
SELECT * FROM products WHERE price BETWEEN 100.00 AND 500.00;
```

**🎯 Use Cases:**
- Price range filtering: `price BETWEEN min AND max`
- Expensive products listing: `price > threshold`
- Budget shopping: `price < max_budget`
- Analytics: price distribution, average price per category

### ⚡ Query Optimization Patterns

#### **🔍 Efficient Query Patterns**
```cql
-- ✅ GOOD: Query by partition key (fastest)
SELECT * FROM products WHERE id = f767c2cb-215d-469e-a3be-c6e40a6cf47f;

-- ✅ GOOD: Secondary index with LIMIT
SELECT * FROM products WHERE category = 'Electronics' LIMIT 50;

-- ✅ GOOD: Range queries на indexed columns
SELECT * FROM products WHERE price > 1000 AND price < 5000 LIMIT 20;

-- ⚠️ AVOID: Full table scan (очень медленно)
SELECT * FROM products WHERE description CONTAINS 'iPhone';

-- ❌ BAD: Multiple secondary index conditions (может быть медленно)
SELECT * FROM products WHERE category = 'Electronics' AND price > 1000;
```

#### **📊 Pagination Strategy**
```python
# Token-based pagination для больших результатов
async def get_products_paginated(category: str, page_size: int = 20, token: str = None):
    if token:
        query = "SELECT * FROM products WHERE category = ? AND token(id) > ? LIMIT ?"
        result = await session.execute(query, [category, token, page_size])
    else:
        query = "SELECT * FROM products WHERE category = ? LIMIT ?"
        result = await session.execute(query, [category, page_size])
    
    rows = result.current_rows
    next_token = None
    
    if len(rows) == page_size:
        # Есть следующая страница
        next_token = str(rows[-1].id)
    
    return {
        "products": [dict(row) for row in rows],
        "next_token": next_token,
        "has_more": next_token is not None
    }
```

---

## 🚀 Performance Tuning

### ⚙️ Cassandra Configuration

#### **🏗️ JVM Settings (cassandra-env.sh)**
```bash
# Heap size optimization для development
MAX_HEAP_SIZE="1G"           # 50% от available RAM
HEAP_NEWSIZE="200M"          # 25% от heap size

# GC optimization
JVM_OPTS="$JVM_OPTS -XX:+UseG1GC"
JVM_OPTS="$JVM_OPTS -XX:G1RSetUpdatingPauseTimePercent=5"
JVM_OPTS="$JVM_OPTS -XX:MaxGCPauseMillis=300"
JVM_OPTS="$JVM_OPTS -XX:InitiatingHeapOccupancyPercent=70"

# Production settings (8GB RAM node)
# MAX_HEAP_SIZE="4G"
# HEAP_NEWSIZE="800M"
```

#### **📝 Cassandra.yaml Key Settings**
```yaml
# Network and connectivity
listen_address: 0.0.0.0
rpc_address: 0.0.0.0
broadcast_address: cassandra        # Container name for docker
native_transport_port: 9042

# Performance settings
concurrent_reads: 32               # 16 * number_of_cores
concurrent_writes: 32              # 8 * number_of_drives
concurrent_counter_writes: 32
concurrent_materialized_view_writes: 32

# Memory and caching
file_cache_size_in_mb: 512        # OS page cache
buffer_pool_use_heap_if_exhausted: true
disk_failure_policy: stop
commit_failure_policy: stop

# Timeouts
read_request_timeout_in_ms: 10000  # 10 seconds
write_request_timeout_in_ms: 5000  # 5 seconds
counter_write_request_timeout_in_ms: 10000

# Compaction
compaction_throughput_mb_per_sec: 16
concurrent_compactors: 1
```

### 📊 Connection Pool Optimization

#### **🔗 Python Driver Configuration**
```python
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.policies import DCAwareRoundRobinPolicy
from cassandra.query import SimpleStatement
import ssl

# Production-ready cluster configuration
def create_cassandra_session():
    # Connection pooling settings
    cluster = Cluster(
        contact_points=['cassandra'],  # Docker service name
        port=9042,
        
        # Connection pool settings
        control_connection_timeout=10.0,
        connect_timeout=10.0,
        
        # Load balancing
        load_balancing_policy=DCAwareRoundRobinPolicy(),
        
        # Connection pool limits
        max_schema_agreement_wait=10,
        max_connections_per_host=10,     # Per node
        
        # Retry and timeout policies
        default_retry_policy=None,       # Use driver defaults
        
        # Compression
        compression=True,
        
        # Metrics
        metrics_enabled=True,
    )
    
    # Create session with keyspace
    session = cluster.connect('store')
    
    # Set consistency level
    session.default_consistency_level = ConsistencyLevel.ONE  # Dev
    # session.default_consistency_level = ConsistencyLevel.QUORUM  # Prod
    
    # Connection pool warmup
    warmup_queries = [
        "SELECT * FROM products LIMIT 1",
        "SELECT COUNT(*) FROM products"
    ]
    
    for query in warmup_queries:
        try:
            session.execute(query)
        except Exception as e:
            logger.warning(f"Warmup query failed: {e}")
    
    return session

# Async session wrapper
class AsyncCassandraClient:
    def __init__(self):
        self.session = create_cassandra_session()
        self.prepared_statements = {}
    
    def prepare_statement(self, query: str) -> str:
        """Prepare и cache CQL statements для performance"""
        if query not in self.prepared_statements:
            self.prepared_statements[query] = self.session.prepare(query)
        return self.prepared_statements[query]
    
    async def execute_async(self, query: str, parameters: list = None):
        """Execute query асинхронно"""
        if parameters:
            prepared = self.prepare_statement(query)
            future = self.session.execute_async(prepared, parameters)
        else:
            future = self.session.execute_async(query)
        
        # Ожидание результата
        result = future.result()
        return result
```

---

## 📊 Мониторинг и наблюдаемость

### 🔍 MCAC (DataStax Metric Collector Agent)

#### **📈 Собираемые метрики**
```yaml
# JVM Metrics
- jvm.memory.heap.used              # Heap memory usage
- jvm.memory.heap.max               # Maximum heap
- jvm.gc.collections.count          # GC events count
- jvm.gc.collections.time           # GC time spent
- jvm.threads.count                 # Active threads

# Cassandra Internal Metrics  
- org.apache.cassandra.metrics.Table.ReadLatency.*
- org.apache.cassandra.metrics.Table.WriteLatency.*
- org.apache.cassandra.metrics.Table.LiveSSTableCount
- org.apache.cassandra.metrics.Table.PendingFlushes
- org.apache.cassandra.metrics.ClientRequest.Read.Latency.*
- org.apache.cassandra.metrics.ClientRequest.Write.Latency.*

# Connection Pool Metrics
- org.apache.cassandra.metrics.Connection.ConnectedNativeClients
- org.apache.cassandra.metrics.Connection.TotalTimeouts.*

# Storage Metrics
- org.apache.cassandra.metrics.Storage.Load                    # Disk usage
- org.apache.cassandra.metrics.Storage.Exceptions.Count        # Storage exceptions
- org.apache.cassandra.metrics.CommitLog.PendingTasks         # Commit log queue
```

#### **⚙️ MCAC Configuration**
```yaml
# metric-collector.yaml
mcac:
  # Data collection
  collectd:
    enabled: true
    interval: 10           # 10-second intervals
    
  # Prometheus integration
  prometheus:
    enabled: true
    port: 9103
    host: 0.0.0.0
    
  # Insights collection
  insights:
    enabled: false         # Disable для privacy в dev
    
  # Filtering
  filtering:
    enabled: true
    allow:
      - "org.apache.cassandra.metrics.*"
      - "jvm.*"
    deny:
      - "org.apache.cassandra.metrics.Table.products.*SSTableCount*"

# Docker integration
environment:
  - MCAC_YAML=/opt/mcac/config/metric-collector.yaml
  - JVM_EXTRA_OPTS=-javaagent:/opt/mcac/lib/datastax-mcac-agent.jar
```

### 📊 Grafana Dashboards

#### **🏗️ Cassandra Overview Dashboard**
```json
{
  "dashboard": {
    "title": "Cassandra Overview",
    "panels": [
      {
        "title": "Read/Write Latency P99",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, rate(org_apache_cassandra_metrics_ClientRequest_Read_Latency[5m]))",
            "legendFormat": "Read P99"
          },
          {
            "expr": "histogram_quantile(0.99, rate(org_apache_cassandra_metrics_ClientRequest_Write_Latency[5m]))", 
            "legendFormat": "Write P99"
          }
        ]
      },
      {
        "title": "Requests per Second",
        "type": "graph", 
        "targets": [
          {
            "expr": "rate(org_apache_cassandra_metrics_ClientRequest_Read_Count[5m])",
            "legendFormat": "Reads/sec"
          },
          {
            "expr": "rate(org_apache_cassandra_metrics_ClientRequest_Write_Count[5m])",
            "legendFormat": "Writes/sec"
          }
        ]
      },
      {
        "title": "JVM Heap Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "jvm_memory_heap_used{instance=\"cassandra:9103\"}",
            "legendFormat": "Used Heap"
          },
          {
            "expr": "jvm_memory_heap_max{instance=\"cassandra:9103\"}",
            "legendFormat": "Max Heap"
          }
        ]
      }
    ]
  }
}
```

#### **🎯 Products Table Specific Metrics**
```json
{
  "title": "Products Table Performance",
  "panels": [
    {
      "title": "Products Table Read Latency",
      "targets": [
        {
          "expr": "org_apache_cassandra_metrics_Table_store_products_ReadLatency_99thPercentile",
          "legendFormat": "Products Read P99"
        }
      ]
    },
    {
      "title": "SSTable Count",
      "targets": [
        {
          "expr": "org_apache_cassandra_metrics_Table_store_products_LiveSSTableCount",
          "legendFormat": "Live SSTables"
        }
      ]
    },
    {
      "title": "Pending Compactions",
      "targets": [
        {
          "expr": "org_apache_cassandra_metrics_Table_store_products_PendingCompactions",
          "legendFormat": "Pending Compactions"
        }
      ]
    }
  ]
}
```

---

## 🔧 Операционные процедуры

### 🚀 Инициализация и миграции

#### **📋 Schema Creation Script**
```bash
#!/bin/bash
# scripts/cassandra_maintenance.sh

# Wait for Cassandra to be ready
echo "Waiting for Cassandra to start..."
until cqlsh cassandra -e "DESCRIBE KEYSPACES" >/dev/null 2>&1; do
    echo "Cassandra not ready yet, waiting 5 seconds..."
    sleep 5
done

echo "Cassandra is ready! Creating schema..."

# Create keyspace and tables
cqlsh cassandra <<EOF
-- Create keyspace
CREATE KEYSPACE IF NOT EXISTS store
WITH replication = {
    'class': 'SimpleStrategy',
    'replication_factor': 1
} AND durable_writes = true;

USE store;

-- Create products table
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY,
    name TEXT,
    category TEXT,
    price DECIMAL,
    quantity INT,
    description TEXT,
    manufacturer TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
) WITH gc_grace_seconds = 3600;

-- Create indexes
CREATE INDEX IF NOT EXISTS products_category_idx ON products (category);
CREATE INDEX IF NOT EXISTS products_price_idx ON products (price);

-- Verify schema
DESCRIBE TABLE products;
SELECT COUNT(*) FROM products;

EOF

echo "Schema creation completed!"
```

#### **📦 Sample Data Loading**
```bash
#!/bin/bash
# scripts/add_20000_products.sh

echo "Loading sample products data..."

cqlsh cassandra <<EOF
USE store;

-- Sample products for testing
INSERT INTO products (id, name, category, price, quantity, description, manufacturer, created_at, updated_at)
VALUES (
    now(),
    'iPhone 14 Pro',
    'Electronics',
    99999.99,
    50,
    'Latest Apple smartphone with A16 Bionic chip',
    'Apple Inc.',
    toTimestamp(now()),
    toTimestamp(now())
);

INSERT INTO products (id, name, category, price, quantity, description, manufacturer, created_at, updated_at)
VALUES (
    now(),
    'MacBook Pro 16',
    'Electronics', 
    249999.99,
    25,
    'Professional laptop with M2 Pro chip',
    'Apple Inc.',
    toTimestamp(now()),
    toTimestamp(now())
);

-- Add more sample products...
-- (Script генерирует 20,000 тестовых товаров)

EOF

echo "Sample data loaded successfully!"
```

### 🔧 Maintenance Operations

#### **🧹 Compaction Management**
```bash
# Manual compaction для оптимизации performance
docker exec cassandra nodetool compact store products

# Repair операция для consistency
docker exec cassandra nodetool repair store

# Cleanup unused data
docker exec cassandra nodetool cleanup store

# Check table statistics
docker exec cassandra nodetool tablestats store.products
```

#### **📊 Performance Analysis**
```bash
# Current latencies
docker exec cassandra nodetool proxyhistograms

# Table-specific stats
docker exec cassandra nodetool tablestats store.products

# Compaction statistics
docker exec cassandra nodetool compactionstats

# Ring status и token distribution
docker exec cassandra nodetool ring

# JVM memory usage
docker exec cassandra nodetool info
```

### 🗄️ Backup & Recovery

#### **💾 Snapshot Creation**
```bash
#!/bin/bash
# Создание снапшота для backup

SNAPSHOT_NAME="products_backup_$(date +%Y%m%d_%H%M%S)"

echo "Creating snapshot: $SNAPSHOT_NAME"
docker exec cassandra nodetool snapshot -t $SNAPSHOT_NAME store

# List snapshots
docker exec cassandra nodetool listsnapshots

echo "Snapshot created: $SNAPSHOT_NAME"
```

#### **🔄 Data Export/Import**
```bash
# Export data to CSV
docker exec cassandra cqlsh -e "
COPY store.products TO '/tmp/products_export.csv' 
WITH HEADER = TRUE;"

# Import data from CSV
docker exec cassandra cqlsh -e "
COPY store.products FROM '/tmp/products_import.csv'
WITH HEADER = TRUE;"
```

---

## 🚨 Troubleshooting

### ⚠️ Common Issues

#### **🔍 Connection Problems**
```bash
# Check if Cassandra is running
docker ps | grep cassandra

# Check logs for errors
docker logs cassandra --tail 100

# Test connectivity
docker exec cassandra cqlsh -e "DESCRIBE KEYSPACES;"

# Network connectivity test
docker exec backend curl -v telnet://cassandra:9042
```

#### **📊 Performance Issues**
```bash
# Check current latencies
docker exec cassandra nodetool proxyhistograms

# Look for slow queries in logs
docker logs cassandra | grep "slow query"

# Check if compaction is running
docker exec cassandra nodetool compactionstats

# Memory usage analysis
docker exec cassandra nodetool info | grep -E "(Heap|Load)"
```

#### **💾 Storage Problems**
```bash
# Check disk usage
docker exec cassandra df -h

# SSTable count per table
docker exec cassandra nodetool tablestats store.products | grep "SSTable count"

# Pending compactions
docker exec cassandra nodetool tpstats | grep CompactionExecutor
```

### 📋 Health Check Procedures

#### **🏥 Automated Health Checks**
```python
# health_check.py
import asyncio
from cassandra.cluster import Cluster
import logging

async def cassandra_health_check():
    """Comprehensive Cassandra health check"""
    try:
        cluster = Cluster(['cassandra'], port=9042)
        session = cluster.connect('store')
        
        # Basic connectivity test
        result = session.execute("SELECT COUNT(*) FROM products")
        count = result.one()[0]
        
        # Latency test
        import time
        start_time = time.time()
        session.execute("SELECT * FROM products LIMIT 10")
        latency = (time.time() - start_time) * 1000
        
        # Schema validation
        tables = session.execute("SELECT table_name FROM system_schema.tables WHERE keyspace_name='store'")
        table_names = [row.table_name for row in tables]
        
        health_status = {
            "status": "healthy",
            "products_count": count,
            "query_latency_ms": round(latency, 2),
            "tables": table_names,
            "timestamp": time.time()
        }
        
        session.shutdown()
        cluster.shutdown()
        
        return health_status
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }

if __name__ == "__main__":
    health = asyncio.run(cassandra_health_check())
    print(f"Cassandra Health: {health}")
```

#### **📊 Performance Baseline**
```yaml
# Expected performance metrics для development environment:
acceptable_thresholds:
  read_latency_p99: 50ms           # 99th percentile read latency
  write_latency_p99: 30ms          # 99th percentile write latency
  connection_timeouts: <1%         # Connection timeout rate
  heap_usage: <80%                 # JVM heap utilization
  disk_usage: <70%                 # Disk space utilization
  rps_capacity: 1000+              # Requests per second capacity

alert_conditions:
  critical:
    - read_latency_p99 > 500ms
    - write_latency_p99 > 200ms  
    - heap_usage > 90%
    - disk_usage > 85%
  
  warning:
    - read_latency_p99 > 100ms
    - write_latency_p99 > 50ms
    - heap_usage > 70%
    - disk_usage > 70%
```

---

## 📚 Дополнительные ресурсы

### 🔗 Полезные ссылки
- [Apache Cassandra Documentation](https://cassandra.apache.org/doc/)
- [DataStax Python Driver](https://docs.datastax.com/en/developer/python-driver/)
- [CQL Reference](https://cassandra.apache.org/doc/latest/cql/)
- [MCAC Documentation](https://docs.datastax.com/en/mcac/6.8/)

### 📖 Best Practices
- **Query Design**: Always design tables around your queries, not entities
- **Partition Size**: Keep partitions under 100MB, ideally under 10MB
- **Secondary Indexes**: Use sparingly, prefer denormalization
- **Consistency**: Choose appropriate consistency levels for your use case
- **Monitoring**: Always monitor query latencies и resource usage
- **Compaction**: Monitor и tune compaction strategies для your workload
