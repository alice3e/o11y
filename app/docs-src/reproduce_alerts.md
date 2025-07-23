# Как воспроизвести алерты

В рамках домашнего задания по Observability необходимо продемонстрировать работу алертов системы мониторинга.

## Настройка окружения

1. **Запустите проект:**
   ```bash
   cd infra
   docker-compose up -d
   ```

2. **Проверьте статус сервисов:**
   ```bash
   ./quick-commands.sh status
   ```

3. **Создайте товары для тестирования:**
   ```bash
   ./quick-commands.sh seed-fast
   ```

## Быстрое воспроизведение алертов

Используйте скрипт быстрых команд:

```bash
cd infra

# 1. Smoke test - проверка работоспособности
./quick-commands.sh smoke

# 2. Load test - нормальная нагрузка (алерты могут сработать)
./quick-commands.sh load

# 3. Stress test - гарантированное срабатывание алертов
./quick-commands.sh stress
```

## Алерт 1: Превышение времени ответа API (P99 > 500ms)

**Способ 1: Через Locust UI**
1. Откройте http://localhost/locust/
2. Настройте параметры:
   - Users: 200-300
   - Spawn rate: 20 users/sec
   - Host: http://nginx (уже настроен)
3. Запустите тест на 5-10 минут

**Способ 2: Через quick-commands**
```bash
./quick-commands.sh stress
```

## Алерт 2: Превышение RPS в базе данных (> 100)

**Способ 1: Интенсивная работа с товарами**
1. Откройте http://localhost/locust/
2. Выберите классы: AdminUser, StressUser
3. Настройте: 100+ пользователей, 15+ spawn rate
4. Запустите тест с фокусом на создание/обновление товаров

**Способ 2: Автоматический стресс-тест**
```bash
./quick-commands.sh stress
```

## Мониторинг алертов

### Проверка срабатывания алертов

1. **Grafana:** http://localhost:3000
   - Переходите на дашборды User Service, Nginx, Cassandra
   - Следите за метриками P99 latency, RPS, error rate

2. **Prometheus:** http://localhost:9090
   - Проверяйте rules и alerts
   - Смотрите активные алерты в разделе Alerts

3. **Locust UI:** http://localhost/locust/
   - Отслеживайте RPS, response times, failure rate
   - Смотрите распределение по типам пользователей

### Ожидаемые результаты

При корректной работе тестирования вы увидите:
- Рост P99 latency выше 500ms в Grafana
- Увеличение Database RPS выше 100 в дашборде Cassandra  
- Алерты в состоянии "Firing" в Prometheus
- Увеличение error rate в Locust UI при высокой нагрузке

### Полезные команды

```bash
# Мониторинг в реальном времени
./quick-commands.sh monitor

# Просмотр логов сервисов
./quick-commands.sh logs

# Проверка статуса
./quick-commands.sh status

# Очистка и перезапуск при проблемах
./quick-commands.sh cleanup
```
   - Spawn rate: 20 users/second

3. Выберите сценарий "Database Intensive" и запустите тест.

4. Продолжайте тест до тех пор, пока не сработает алерт (обычно 30-60 секунд).

## Проверка алертов

Алерты настроены на отправку уведомлений в Telegram-канал:
[Ссылка на Telegram-канал с алертами](https://t.me/your_channel_name)

Также вы можете проверить статус алертов в интерфейсе Grafana:
```
http://localhost/grafana/alerts
```
