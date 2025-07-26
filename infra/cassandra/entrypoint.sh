#!/bin/bash

# Скрипт для настройки OpenTelemetry в Cassandra при запуске
# Добавляем переменные окружения в JVM_OPTS если они не заданы через docker-compose

# Проверяем наличие переменных окружения OpenTelemetry
if [ -n "$OTEL_EXPORTER_OTLP_ENDPOINT" ]; then
    export JVM_OPTS="$JVM_OPTS -Dotel.exporter.otlp.endpoint=$OTEL_EXPORTER_OTLP_ENDPOINT"
fi

if [ -n "$OTEL_SERVICE_NAME" ]; then
    export JVM_OPTS="$JVM_OPTS -Dotel.service.name=$OTEL_SERVICE_NAME"
fi

if [ -n "$OTEL_RESOURCE_ATTRIBUTES" ]; then
    export JVM_OPTS="$JVM_OPTS -Dotel.resource.attributes=$OTEL_RESOURCE_ATTRIBUTES"
fi

# Настройки для оптимальной работы OpenTelemetry с Cassandra
export JVM_OPTS="$JVM_OPTS -Dotel.traces.exporter=otlp"
export JVM_OPTS="$JVM_OPTS -Dotel.metrics.exporter=none"  
export JVM_OPTS="$JVM_OPTS -Dotel.logs.exporter=none"
export JVM_OPTS="$JVM_OPTS -Dotel.instrumentation.cassandra.enabled=true"
export JVM_OPTS="$JVM_OPTS -Dotel.instrumentation.runtime-metrics.enabled=true"

echo "OpenTelemetry configuration applied to Cassandra JVM"
echo "JVM_OPTS: $JVM_OPTS"

# Запускаем стандартный entrypoint Cassandra
exec /usr/local/bin/docker-entrypoint.sh "$@"
