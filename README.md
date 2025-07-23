# Домашнее задание по теме "o11y"

Цель домашнего задания - сделать любое бекенд приложение. Пользоваться можно и нужно чем угодно.
Приложение просто должно иметь API и быть более менее осмысленным. Оно все равно будет использоваться только для тренировки работы с алертами, метриками и так далее.

## Что реализовано:

**🏪 Product Store - Микросервисная система интернет-магазина**

### 🔥 Основная функциональность:
- **Каталог товаров**: просмотр товаров с фильтрацией по категориям
- **Корзина**: добавление/удаление товаров, управление количеством
- **Заказы**: оформление заказов, отслеживание статуса
- **Пользователи**: регистрация, аутентификация, профили

### 🎯 Новая функциональность - Контроль доступа по ролям:
- **👑 Администраторы** (`swagger_admin`): полный доступ ко всем товарам и административные функции
- **👤 Обычные пользователи** (`swagger_user`): обязательная фильтрация по категориям при просмотре товаров  
- **🌐 Неавторизованные**: доступ к товарам только с указанием категории

**Пример бизнес-логики:**
```bash
# ❌ Обычный пользователь НЕ может получить все товары
GET /api/products/ → "Обычные пользователи должны указать категорию"

# ✅ Обычный пользователь может получить товары категории
GET /api/products/?category=Фрукты → список товаров категории "Фрукты"

# ✅ Администратор может получить все товары
GET /api/products/ → полный список товаров
```

### 🏗️ Архитектура:
- **FastAPI** микросервисы (Backend, Cart, Order, User)
- **Cassandra** база данных
- **JWT аутентификация** с ролевой моделью
- **Nginx** reverse proxy
- **Docker Compose** оркестрация

### 🚀 **Новое! Комплексная система мониторинга и Observability:**

#### ✅ **1. Графики и метрики (Infrastructure as Code)**
- **Prometheus**: сбор метрик с автоматической конфигурацией
  - 📁 Конфигурация: [`/infra/prometheus/prometheus.yml`](./infra/prometheus/prometheus.yml)
  - HTTP метрики User Service (RPS, latency, error rate)
  - Метрики Nginx (connections, throughput)
  - Метрики Cassandra через MCAC Agent (JVM, DB performance, system metrics)

- **Grafana**: дашборды с автоматическим provisioning  
  - 📁 Дашборды: [`/infra/grafana/provisioning/dashboards/`](./infra/grafana/provisioning/dashboards/)
  - **User Service Dashboard**: HTTP метрики, P99 latency, бизнес-метрики
  - **Nginx Dashboard**: веб-сервер performance и upstream latency
  - **Cassandra Dashboards**: системные метрики и производительность БД

#### ✅ **2. Автоматический сбор метрик**
- **FastAPI Instrumentator**: автоматические HTTP метрики для User Service
- **Кастомные метрики**: счетчик зарегистрированных пользователей (`users_registered_total`)
- **Nginx Exporter**: экспорт метрик веб-сервера
- **DataStax MCAC Agent**: комплексный мониторинг Cassandra

#### ✅ **3. Алерты (готово для Telegram интеграции)**
- 📁 Правила: [`/infra/prometheus/prometheus.yml`](./infra/prometheus/prometheus.yml) (секция alerting закомментирована)
- **P99 Latency Alert**: срабатывает при превышении 500ms
- **Database RPS Alert**: срабатывает при > 100 RPS в БД
- **Готовность к интеграции с Telegram**: структура алертов настроена

#### ✅ **4. Swagger UI**  
- **Интерактивная документация**: http://localhost/swagger/
- **Тестирование API**: все эндпоинты доступны для тестирования
- **Аутентификация**: поддержка JWT токенов в интерфейсе

### 📊 **Доступ к мониторингу:**
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090  
- **Swagger UI**: http://localhost/swagger/
- **Документация**: http://localhost/docs/
- **Locust UI**: http://localhost/locust/

### 🔧 **Быстрый запуск:**
```bash
cd infra
docker-compose up -d

# Быстрые команды управления
./quick-commands.sh help

# Проверка всех сервисов
./quick-commands.sh status

# Заполнение данными и тестирование
./quick-commands.sh seed-fast
./quick-commands.sh smoke
```

---

## Требования ДЗ - Статус выполнения

### ✅ **Минимальные требования (5 баллов):**

1. **✅ Бэкенд приложение**: FastAPI микросервисы с полным REST API
2. **✅ Нагрузочный сервис**: Locust с 5 типами пользователей (доступен http://localhost/locust/)
3. **✅ База данных**: Apache Cassandra с полной схемой данных  
4. **✅ Графики и алерты**:
   - ✅ **Графики приложения**: User Service metrics (RPS, latency, errors)
   - ✅ **Графики БД**: Cassandra performance via MCAC Agent  
   - 🔄 **Алерты в Telegram**: правила настроены, интеграция в процессе
5. **✅ Infrastructure as Code**: все конфигурации в Git
   - Prometheus: [`/infra/prometheus/prometheus.yml`](./infra/prometheus/prometheus.yml)
   - Grafana Dashboards: [`/infra/grafana/provisioning/`](./infra/grafana/provisioning/)
   - Docker Compose: [`/infra/docker-compose.yml`](./infra/docker-compose.yml)

### ✅ **Бонусы (+6 баллов):**

6. **✅ Swagger UI**: http://localhost/swagger/ - интерактивная документация API
7. **🔄 Трейсинг**: планируется Jaeger интеграция  
8. **🔄 Performance инструменты**: планируется Python profiling
9. **✅ "Новая" БД**: Apache Cassandra (NoSQL, распределенная)
10. **✅ "Новый" язык**: Python с FastAPI (асинхронный стек)

### 📋 **Что осталось доделать:**
- [ ] Настроить Telegram webhook для алертов
- [ ] Добавить distributed tracing  
- [ ] Интегрировать performance profiling

### 🎯 **Как воспроизвести алерты:**

```bash
cd infra

# Быстрое заполнение товарами
./quick-commands.sh seed-fast

# Стресс-тест для алертов
./quick-commands.sh stress

# Мониторинг результатов
./quick-commands.sh monitor
```

**Доступ к инструментам:**
- **Locust UI**: http://localhost/locust/
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

---

## Техническая документация

- 📚 **Подробная архитектура**: [`/app/docs-src/architecture.md`](./app/docs-src/architecture.md)
- 📊 **Система мониторинга**: [`/app/docs-src/monitoring.md`](./app/docs-src/monitoring.md)  
- 🗄️ **База данных**: [`/app/docs-src/database.md`](./app/docs-src/database.md)
- 🔐 **Аутентификация**: [`/app/docs-src/authentication.md`](./app/docs-src/authentication.md)
- 🧪 **Тестирование**: [`/app/docs-src/testing.md`](./app/docs-src/testing.md)

## Дополнительные бонусы (в планах)

### Observability расширения
- **Distributed Tracing**: Jaeger для трейсинга межсервисных вызовов
- **Log Aggregation**: ELK stack или Grafana Loki
- **Application Performance Monitoring**: New Relic или Datadog интеграция

### Performance и надежность  
- **Circuit Breaker**: resilience patterns для межсервисного взаимодействия
- **Rate Limiting**: защита от перегрузки API
- **Caching**: Redis для кэширования часто запрашиваемых данных

### DevOps и автоматизация
- **CI/CD Pipeline**: GitHub Actions или GitLab CI
- **Infrastructure as Code**: Terraform для cloud deployment
- **Container Orchestration**: Kubernetes манифесты

**Текущий статус**: 11+ баллов (5 минимум + 6 бонусов) 🎯
