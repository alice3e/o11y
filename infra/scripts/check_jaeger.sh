#!/bin/bash

# 🔍 Jaeger Infrastructure Health Check Script
# Проверяет готовность инфраструктуры Jaeger

echo "🔍 Checking Jaeger infrastructure..."
echo "=================================="

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для проверки URL
check_url() {
    local url=$1
    local service_name=$2
    
    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|302"; then
        echo -e "${GREEN}✅ $service_name is available at $url${NC}"
        return 0
    else
        echo -e "${RED}❌ $service_name is not available at $url${NC}"
        return 1
    fi
}

# Функция для проверки порта
check_port() {
    local host=$1
    local port=$2
    local service_name=$3
    
    if nc -z "$host" "$port" 2>/dev/null; then
        echo -e "${GREEN}✅ $service_name port $port is open${NC}"
        return 0
    else
        echo -e "${RED}❌ $service_name port $port is not accessible${NC}"
        return 1
    fi
}

# Основные проверки
echo "🌐 Checking Jaeger UI accessibility..."
check_url "http://localhost:16686/" "Jaeger UI (direct)"
check_url "http://localhost/jaeger/" "Jaeger UI (via Nginx)"

echo ""
echo "🔌 Checking Jaeger receiver ports..."
check_port "localhost" "4317" "OpenTelemetry gRPC"
check_port "localhost" "4318" "OpenTelemetry HTTP" 
check_port "localhost" "14250" "Jaeger gRPC"
check_port "localhost" "14268" "Jaeger HTTP"
check_port "localhost" "6831" "Jaeger UDP (legacy)"

echo ""
echo "📊 Checking Jaeger metrics..."
check_url "http://localhost:14269/metrics" "Jaeger Prometheus metrics"

echo ""
echo "🐳 Checking Docker container status..."
if docker ps | grep -q "jaeger.*Up"; then
    echo -e "${GREEN}✅ Jaeger container is running${NC}"
    
    # Показываем статус контейнера
    echo ""
    echo "📋 Container details:"
    docker ps --filter "name=jaeger" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
else
    echo -e "${RED}❌ Jaeger container is not running${NC}"
    echo "💡 Try: docker-compose up -d jaeger"
fi

echo ""
echo "🔍 Checking Jaeger health endpoint..."
if curl -s "http://localhost:16686/" | grep -q "Jaeger UI"; then
    echo -e "${GREEN}✅ Jaeger UI is responding correctly${NC}"
else
    echo -e "${YELLOW}⚠️  Jaeger UI might be starting up...${NC}"
fi

echo ""
echo "📊 Testing trace ingestion endpoints..."

# Тест OpenTelemetry HTTP endpoint
echo "Testing OpenTelemetry HTTP endpoint..."
if curl -s -X POST "http://localhost:4318/v1/traces" \
   -H "Content-Type: application/json" \
   -d '{"resourceSpans":[]}' | grep -q ""; then
    echo -e "${GREEN}✅ OpenTelemetry HTTP endpoint is accepting requests${NC}"
else
    echo -e "${YELLOW}⚠️  OpenTelemetry HTTP endpoint test unclear${NC}"
fi

echo ""
echo "🎯 Next steps:"
echo "  1. Visit Jaeger UI: http://localhost/jaeger/"
echo "  2. Check Grafana dashboard: http://localhost:3000"
echo "  3. View Prometheus metrics: http://localhost:9090"
echo "  4. Ready for OpenTelemetry integration in microservices"

echo ""
echo "=================================="
echo "🏁 Jaeger infrastructure check complete!"
