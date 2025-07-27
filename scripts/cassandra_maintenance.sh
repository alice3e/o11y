#!/bin/bash

# Скрипт для обслуживания Cassandra: очистка tombstone-ячеек и компактификация

set -e

echo "🔧 Starting Cassandra maintenance..."

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функция для логирования
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Проверяем, запущен ли Docker Compose
if ! docker-compose -f infra/docker-compose.yml ps cassandra | grep -q "Up"; then
    error "Cassandra container is not running. Please start it first:"
    echo "  cd infra && docker-compose up -d cassandra"
    exit 1
fi

log "✅ Cassandra container is running"

# 1. Настройка gc_grace_seconds для таблицы products
log "🔧 Setting gc_grace_seconds for products table..."
docker-compose -f infra/docker-compose.yml exec cassandra cqlsh -e "
USE store;
ALTER TABLE products WITH gc_grace_seconds = 3600;
DESCRIBE TABLE products;
" || warn "Could not set gc_grace_seconds (table may not exist yet)"

# 2. Выполнение компактификации
log "🗜️  Starting compaction for store.products table..."
docker-compose -f infra/docker-compose.yml exec cassandra nodetool compact store products || warn "Compaction failed or table does not exist"

# 3. Проверка статуса компактификации
log "📊 Checking compaction status..."
docker-compose -f infra/docker-compose.yml exec cassandra nodetool compactionstats || warn "Could not get compaction stats"

# 4. Очистка снапшотов (опционально)
log "🧹 Cleaning up old snapshots..."
docker-compose -f infra/docker-compose.yml exec cassandra nodetool clearsnapshot store || warn "Could not clean snapshots"

# 5. Информация о состоянии таблицы
log "📋 Table information:"
docker-compose -f infra/docker-compose.yml exec cassandra nodetool tablestats store.products || warn "Could not get table stats"

log "✅ Cassandra maintenance completed!"
log "💡 Tombstone warnings should decrease after this maintenance."
log "💡 If warnings persist, consider:"
log "   - Reducing data insertion/deletion rate"
log "   - Implementing proper data modeling"
log "   - Running this maintenance more frequently"

echo ""
echo "📈 To monitor the effect, check the logs for tombstone warnings:"
echo "   docker-compose -f infra/docker-compose.yml logs -f backend | grep tombstone"
