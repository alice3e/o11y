# 🚨 Воспроизведение алертов мониторинга

Пошаговое руководство для демонстрации работы системы мониторинга и алертов Product Store в рамках демонстрации observability возможностей.

## 🎯 Цель демонстрации

Показать работу комплексной системы мониторинга:
- **📊 Сбор метрик** в реальном времени
- **🚨 Срабатывание алертов** при превышении пороговых значений
- **📈 Визуализация** производительности в Grafana
- **⚡ Нагрузочное тестирование** с помощью Locust

---

## 🏁 Быстрый старт

### 1. 🚀 Запуск системы

```bash
# Переход в директорию инфраструктуры
cd infra

# Запуск всех сервисов
docker-compose up -d

# Проверка статуса (все сервисы должны быть healthy)
docker-compose ps

# Ожидание готовности всех сервисов (особенно Cassandra)
sleep 60
```

### 2. 📊 Проверка доступности интерфейсов

| Сервис | URL | Описание |
|--------|-----|----------|
| **🎯 Locust** | [http://localhost:8089](http://localhost:8089) | Нагрузочное тестирование |
| **📊 Grafana** | [http://localhost:3000](http://localhost:3000) | Мониторинг и алерты |
| **📈 Prometheus** | [http://localhost:9090](http://localhost:9090) | Метрики и правила |
| **🌐 Application** | [http://localhost](http://localhost) | Product Store API |
| **📚 Swagger** | [http://localhost/swagger](http://localhost/swagger) | API документация |

### 3. 🌱 Создание тестовых данных

```bash
# Получение админского токена
ADMIN_TOKEN=$(curl -s -X POST http://localhost/user-api/token \
  -d "username=swagger_admin&password=admin123" \
  | jq -r '.access_token')

# Создание тестовых товаров (для реалистичной нагрузки)
for i in {1..50}; do
  curl -s -X POST http://localhost/api/products/ \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"Load Test Product $i\",
      \"category\": \"Тест\",
      \"price\": $((RANDOM % 200 + 50)).99,
      \"stock_count\": $((RANDOM % 100 + 50)),
      \"description\": \"Product for load testing\",
      \"manufacturer\": \"Test Corp\"
    }" > /dev/null
done

echo "✅ Created 50 test products for load testing"
```

---

## 🚨 Сценарии воспроизведения алертов

### 🔥 Сценарий 1: High API Latency Alert

**Цель**: Превышение P99 latency > 500ms

#### 📋 Шаги выполнения:

1. **Откройте Grafana** [http://localhost:3000](http://localhost:3000)
   - Username: `admin`
   - Password: `admin`

2. **Перейдите на Backend Dashboard**
   - Найдите панель "P99 Response Time"
   - Текущее значение должно быть < 100ms

3. **Откройте Locust** [http://localhost:8089](http://localhost:8089)

4. **Настройте нагрузочный тест:**
   ```
   Number of users: 200
   Spawn rate: 20 users/second
   Host: http://nginx (предустановлено)
   ```

5. **Запустите тест** и наблюдайте:
   - В Locust: рост Response Time
   - В Grafana: увеличение P99 latency

#### ⏱️ Ожидаемый результат:
- **Через 2-3 минуты**: P99 latency > 500ms
- **В Grafana**: Алерт "High P99 Latency" в состоянии FIRING
- **В Prometheus**: Активный алерт в разделе Alerts

### ⚡ Сценарий 2: High Database RPS Alert

**Цель**: Превышение RPS к базе данных > 100

#### 📋 Шаги выполнения:

1. **Откройте Cassandra Dashboard** в Grafana
   - Найдите панель "Database RPS"
   - Текущее значение должно быть < 20

2. **Настройте интенсивный тест в Locust:**
   ```
   Number of users: 300
   Spawn rate: 30 users/second
   Duration: 10 minutes
   ```

3. **Запустите тест** с фокусом на операции с товарами

#### ⏱️ Ожидаемый результат:
- **Через 1-2 минуты**: Database RPS > 100
- **В Grafana**: Алерт "High Database RPS" в состоянии FIRING

### 💾 Сценарий 3: High Memory Usage Alert

**Цель**: Превышение использования памяти > 80%

#### 📋 Шаги выполнения:

1. **Откройте System Metrics Dashboard**
2. **Запустите стресс-тест:**
   ```
   Number of users: 500
   Spawn rate: 50 users/second
   Duration: 15 minutes
   ```

3. **Мониторьте Memory Usage**

#### ⏱️ Ожидаемый результат:
- **Через 5-10 минут**: Memory usage > 80%
- **Алерт**: "High Memory Usage" активен

### 📊 Сценарий 4: High Error Rate Alert

**Цель**: Превышение процента ошибок > 5%

#### 📋 Шаги выполнения:

1. **Запустите экстремальную нагрузку:**
   ```
   Number of users: 1000
   Spawn rate: 100 users/second
   Duration: 5 minutes
   ```

2. **Мониторьте Error Rate** в Nginx Dashboard

#### ⏱️ Ожидаемый результат:
- **Через 2-3 минуты**: Error rate > 5%
- **Алерт**: "High Error Rate" в состоянии FIRING

---

## 📊 Мониторинг алертов

### 🎯 В Prometheus

**URL**: [http://localhost:9090/alerts](http://localhost:9090/alerts)

**Проверка активных алертов:**
```
1. Переходите в раздел "Status" → "Rules"
2. Находите правила в состоянии "FIRING"
3. Проверяете детали срабатывания
```

**Типичные алерты в активном состоянии:**
- ✅ `HighP99Latency` - FIRING при нагрузке > 200 пользователей
- ✅ `HighDatabaseRPS` - FIRING при интенсивной работе с БД
- ✅ `HighMemoryUsage` - FIRING при длительной нагрузке
- ✅ `HighErrorRate` - FIRING при экстремальной нагрузке

### 📈 В Grafana

**URL**: [http://localhost:3000](http://localhost:3000)

**Основные дашборды для мониторинга:**

#### 🏪 Backend Service Dashboard
- **P99 Response Time**: текущая задержка API
- **Request Rate**: количество запросов в секунду
- **Error Rate**: процент ошибочных запросов
- **CPU/Memory Usage**: ресурсы Backend сервиса

#### 🗄️ Cassandra Overview Dashboard
- **Database RPS**: операции чтения/записи в секунду
- **Query Latency**: задержка запросов к БД
- **Connection Pool**: использование подключений
- **Storage Metrics**: использование диска

#### 🌐 Nginx Dashboard
- **Request Volume**: общий объем запросов
- **Response Times**: время отклика прокси
- **Status Codes**: распределение HTTP статусов
- **Upstream Health**: состояние backend сервисов

#### 👤 User Service Dashboard
- **Authentication Rate**: количество аутентификаций
- **JWT Token Operations**: операции с токенами
- **Profile Requests**: запросы профилей пользователей

### 🎯 В Locust

**URL**: [http://localhost:8089](http://localhost:8089)

**Ключевые метрики для анализа:**
- **Total Requests**: общее количество запросов
- **Failures**: количество и процент ошибок
- **Response Times**: P50, P95, P99 перцентили
- **RPS**: текущая нагрузка (requests per second)

---

## 🔧 Troubleshooting

### ❗ Сервисы не запускаются

```bash
# Проверка статуса
docker-compose ps

# Проверка логов
docker-compose logs | grep ERROR

# Перезапуск проблемных сервисов
docker-compose restart backend cassandra

# Полная очистка и перезапуск
docker-compose down -v
docker-compose up -d
```

### 📊 Алерты не срабатывают

```bash
# Проверка правил Prometheus
curl http://localhost:9090/api/v1/rules

# Проверка конфигурации алертов
docker exec prometheus cat /etc/prometheus/alert_rules.yml

# Проверка метрик
curl http://localhost:9090/api/v1/query?query=rate\(nginx_http_requests_total\[5m\]\)
```

### ⚡ Низкая нагрузка в Locust

```bash
# Увеличение количества пользователей
# В Locust UI: Users > 300, Spawn rate > 30

# Проверка производительности хост-системы
docker stats

# Оптимизация для максимальной нагрузки
docker-compose up -d --scale backend=2
```

### 🐌 Медленная работа системы

```bash
# Мониторинг ресурсов
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Проверка Cassandra performance
docker exec cassandra nodetool tpstats

# Очистка тестовых данных
curl -X DELETE http://localhost/api/products/cleanup \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## 📋 Чек-лист успешной демонстрации

### ✅ Предварительная подготовка
- [ ] Все сервисы запущены и healthy
- [ ] Grafana доступна с дашбордами
- [ ] Prometheus собирает метрики
- [ ] Locust готов к тестированию
- [ ] Тестовые данные созданы

### ✅ Демонстрация алертов
- [ ] **High P99 Latency** сработал при нагрузке 200+ пользователей
- [ ] **High Database RPS** активен при интенсивной работе с БД
- [ ] **High Memory Usage** сработал при длительной нагрузке
- [ ] **High Error Rate** активен при экстремальной нагрузке

### ✅ Мониторинг работает
- [ ] Метрики отображаются в реальном времени
- [ ] Алерты переходят в состояние FIRING
- [ ] Дашборды показывают корректные данные
- [ ] Система восстанавливается после снижения нагрузки

### ✅ Документация готова
- [ ] Инструкции протестированы
- [ ] Скриншоты алертов сделаны
- [ ] Результаты нагрузочного тестирования зафиксированы
- [ ] Выводы о производительности системы готовы

---

## 🎬 Сценарий презентации (10 минут)

### 1. Обзор архитектуры (2 минуты)
- Микросервисная архитектура Product Store
- Компоненты мониторинга (Prometheus + Grafana)
- Нагрузочное тестирование (Locust)

### 2. Демонстрация baseline метрик (2 минуты)
- Открытие дашбордов Grafana
- Показ текущих метрик в спокойном состоянии
- Обзор настроенных алертов в Prometheus

### 3. Запуск нагрузочного тестирования (3 минуты)
- Настройка и запуск Locust
- Постепенное увеличение нагрузки
- Наблюдение за ростом метрик в реальном времени

### 4. Срабатывание алертов (2 минуты)
- Демонстрация активных алертов в Prometheus
- Показ визуализации в Grafana
- Объяснение причин срабатывания

### 5. Анализ результатов (1 минута)
- Обзор собранных метрик
- Выводы о производительности системы
- Возможности оптимизации

---

**🎯 Цель достигнута**: Продемонстрирована работающая система observability с автоматическими алертами при превышении пороговых значений производительности.
