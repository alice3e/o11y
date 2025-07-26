FROM prom/alertmanager:latest

# Создаем пользователя для безопасности
USER 65534

# Копируем конфигурационный файл
COPY alertmanager.yml /etc/alertmanager/alertmanager.yml

COPY token /etc/alertmanager/token

# Создаем директории для данных
VOLUME ["/alertmanager"]

# Экспонируем порт
EXPOSE 9093

# Команда запуска с параметрами
ENTRYPOINT ["/bin/alertmanager"]
CMD ["--config.file=/etc/alertmanager/alertmanager.yml", \
     "--storage.path=/alertmanager", \
     "--web.external-url=http://localhost:9093", \
     "--cluster.listen-address=0.0.0.0:9094"]
