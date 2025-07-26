# Используем официальный образ Cassandra как основу
FROM cassandra:4.1

ENV MCAC_AGENT_URL=https://github.com/datastax/metric-collector-for-apache-cassandra/releases/download/v0.3.6/datastax-mcac-agent-0.3.6-4.1-beta1.tar.gz
ENV OTEL_JAVA_AGENT_URL=https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v1.33.5/opentelemetry-javaagent.jar

# Устанавливаем утилиты для скачивания и распаковки
RUN apt-get update && apt-get install -y curl tar && rm -rf /var/lib/apt/lists/*

# Создаем директорию для агента
RUN mkdir -p /opt/mcac /opt/otel

# Скачиваем и распаковываем MCAC агент
RUN curl -L ${MCAC_AGENT_URL} | tar -xz -C /opt/mcac --strip-components=1

# Скачиваем OpenTelemetry Java агент
RUN curl -L ${OTEL_JAVA_AGENT_URL} -o /opt/otel/opentelemetry-javaagent.jar

# Активируем агенты, добавляя флаги -javaagent в конфигурацию JVM
RUN echo "-javaagent:/opt/mcac/lib/datastax-mcac-agent.jar" >> /etc/cassandra/jvm-server.options
RUN echo "-javaagent:/opt/otel/opentelemetry-javaagent.jar" >> /etc/cassandra/jvm-server.options

# Копируем скрипт entrypoint
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Используем наш кастомный entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["cassandra", "-f"]
