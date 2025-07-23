# Используем официальный образ Cassandra как основу
FROM cassandra:4.1

ENV MCAC_AGENT_URL https://github.com/datastax/metric-collector-for-apache-cassandra/releases/download/v0.3.6/datastax-mcac-agent-0.3.6-4.1-beta1.tar.gz

# Устанавливаем утилиты для скачивания и распаковки
RUN apt-get update && apt-get install -y curl tar && rm -rf /var/lib/apt/lists/*

# Создаем директорию для агента
RUN mkdir -p /opt/mcac

# Скачиваем и распаковываем агент
RUN curl -L ${MCAC_AGENT_URL} | tar -xz -C /opt/mcac --strip-components=1

# Активируем агент, добавляя флаг -javaagent в конфигурацию JVM
# Это самый надежный способ для Cassandra 4+
RUN echo "-javaagent:/opt/mcac/lib/datastax-mcac-agent.jar" >> /etc/cassandra/jvm-server.options
