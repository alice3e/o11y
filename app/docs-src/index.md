# 🏪 Добро пожаловать в Product Store

Современная микросервисная система интернет-магазина, построенная на принципах Cloud Native архитектуры с полноценной системой мониторинга, трейсинга и observability.

## 🎯 О проекте

Product Store — это комплексная демонстрационная платформа, показывающая лучшие практики современной разработки микросервисных приложений. Система включает в себя четыре основных микросервиса, полную систему мониторинга с трейсингом, нагрузочное тестирование, профилирование производительности и исчерпывающую документацию.

### ✨ Ключевые особенности

- **🏗️ Микросервисная архитектура** с четкой доменной изоляцией и независимыми сервисами
- **🔧 Cloud Native подход** с контейнеризацией, orchestration и современными паттернами
- **📊 Observability by design** с метриками, логами, трейсингом и профилированием
- **🚀 Performance-focused** с оптимизированными NoSQL базами данных и кэшированием
- **🔒 Security-first** с JWT аутентификацией, ролевым доступом и межсервисной авторизацией
- **🧪 Comprehensive testing** с автоматизированным тестированием, мониторингом и алертингом
- **⚡ Real-time processing** с асинхронной обработкой заказов и уведомлениями

# Ссылки на сервисы

http://51.250.7.79:16686/ - jaeger

http://51.250.7.79:3000 - grafana (admin, admin)

http://51.250.7.79/profiles/ - веб сервер  с файлами perf для snakeviz

http://51.250.7.79/docs/ - документация

http://51.250.7.79/locust/ - нагрузочное тестирование

http://51.250.7.79:9090/targets - prometheus

http://51.250.7.79/swagger/ - трогаем ручки (swagger)

---

## 🏗️ Микросервисная архитектура

### Основные компоненты

```mermaid
graph TB
    subgraph "🌐 Gateway Layer"
        NGINX[🌐 Nginx Reverse Proxy<br/>Port 80<br/>API Gateway + Load Balancer]
    end
    
    subgraph "🛍️ Business Services"
        BACKEND[🏪 Backend Service<br/>Port 8000<br/>Products & Catalog<br/>Cassandra Integration]
        CART[🛒 Cart Service<br/>Port 8001<br/>Shopping Cart<br/>Stock Validation]
        ORDER[📦 Order Service<br/>Port 8002<br/>Order Processing<br/>Auto Status Updates]
        USER[👤 User Service<br/>Port 8003<br/>Authentication & Users<br/>Profile Aggregation]
    end
    
    subgraph "🗄️ Data Layer"
        CASSANDRA[🗄️ Apache Cassandra 4.1<br/>Port 9042<br/>NoSQL Database<br/>High Performance Storage]
        MEMORY[💾 In-Memory Storage<br/>Cart, Orders, Users<br/>Fast Access Layer]
    end
    
    subgraph "📊 Observability Stack"
        PROMETHEUS[📊 Prometheus<br/>Port 9090<br/>Metrics Collection]
        GRAFANA[📈 Grafana<br/>Port 3000<br/>7 Specialized Dashboards]
        JAEGER[🔍 Jaeger<br/>Port 16686<br/>Distributed Tracing]
        ALERTMANAGER[🚨 Alertmanager<br/>Port 9093<br/>Alert Management]
    end
    
    subgraph "🧪 Testing & Tools"
        LOCUST[🚀 Locust<br/>Port 8089<br/>Load Testing<br/>Real User Scenarios]
        SWAGGER[📋 Swagger UI<br/>Interactive API Docs]
        DOCS[📖 MkDocs<br/>Project Documentation]
        PROFILER[⚡ Performance Profiler<br/>Code Optimization]
    end
    
    NGINX --> BACKEND
    NGINX --> CART
    NGINX --> ORDER
    NGINX --> USER
    NGINX --> SWAGGER
    NGINX --> DOCS
    NGINX --> LOCUST
    
    BACKEND --> CASSANDRA
    CART --> MEMORY
    ORDER --> MEMORY
    USER --> MEMORY
    
    CART -.->|Validate Stock| BACKEND
    CART -.->|Create Order| ORDER
    ORDER -.->|Notify Status| USER
    USER -.->|Get Cart Data| CART
    USER -.->|Get Orders| ORDER
    
    BACKEND --> PROMETHEUS
    CART --> PROMETHEUS
    ORDER --> PROMETHEUS
    USER --> PROMETHEUS
    CASSANDRA --> PROMETHEUS
    NGINX --> PROMETHEUS
    
    PROMETHEUS --> GRAFANA
    PROMETHEUS --> ALERTMANAGER
    
    BACKEND -.->|Traces| JAEGER
    CART -.->|Traces| JAEGER
    ORDER -.->|Traces| JAEGER
    USER -.->|Traces| JAEGER
```

### Основные сервисы

#### 🏪 Backend Service (Port 8000)
- **Функции**: Управление товарами, каталог, интеграция с Cassandra
- **Особенности**: JWT авторизация, ролевой доступ, автоматические метрики
- **База данных**: Прямой доступ к Apache Cassandra
- **API**: 10+ эндпоинтов для работы с товарами и категориями

#### 🛒 Cart Service (Port 8001)  
- **Функции**: Управление корзиной, валидация остатков, интеграция с заказами
- **Особенности**: In-memory хранение, межсервисные вызовы, бизнес-метрики
- **Интеграция**: Backend (товары), Order Service (создание заказов)
- **API**: Полный CRUD для корзины + checkout функциональность

#### 📦 Order Service (Port 8002)
- **Функции**: Обработка заказов, автоматическое изменение статусов, уведомления
- **Особенности**: Background tasks, асинхронная обработка, автоудаление
- **Жизненный цикл**: CREATED → PROCESSING → SHIPPING → DELIVERED
- **API**: Управление заказами + административные функции

#### 👤 User Service (Port 8003)
- **Функции**: Аутентификация, управление пользователями, агрегация профилей
- **Особенности**: JWT токены, хэширование паролей, межсервисная интеграция
- **Агрегация**: Объединение данных из Cart и Order сервисов
- **API**: Регистрация, вход, профили + интеграционные эндпоинты

---

## 📊 Система мониторинга и observability

### 🎯 Компоненты мониторинга

#### 📊 Prometheus (Port 9090)
- **Сбор метрик** с интервалом 10 секунд
- **8 job targets** для всех сервисов и инфраструктуры
- **Custom метрики** для бизнес-логики
- **Alert rules** с автоматическими уведомлениями

#### 📈 Grafana (Port 3000)
**7 специализированных дашбордов:**
1. **Backend Service** - метрики товаров и Cassandra
2. **Cart Service** - корзины и бизнес-метрики  
3. **Order Service** - заказы и время доставки
4. **User Service** - регистрации и аутентификация
5. **Nginx** - web server метрики и upstream latency
6. **Cassandra Overview** - database performance
7. **Jaeger** - tracing statistics и collector metrics

#### 🔍 Jaeger Tracing
- **All-in-one** конфигурация для разработки
- **OpenTelemetry** интеграция во все сервисы
- **Автоматический трейсинг** HTTP запросов
- **Custom spans** для бизнес-операций
- **In-memory storage** с 50,000 трейсов

#### 🚨 Alertmanager (Port 9093)
- **4 типа алертов**: P99 latency, RPS, error rates
- **Telegram интеграция** для уведомлений
- **Группировка алертов** по severity
- **Auto-resolution** при восстановлении метрик

### 📈 Ключевые метрики

#### HTTP метрики (все сервисы)
- **Request duration** - гистограммы времени ответа
- **Request rate** - RPS по эндпоинтам
- **Error rate** - процент ошибок по статус-кодам
- **Concurrent requests** - активные соединения

#### Бизнес-метрики
- **Cart operations** - добавления/удаления товаров
- **Order lifecycle** - создание, статусы, доставка
- **User registrations** - новые пользователи
- **Product views** - популярность товаров

#### Infrastructure метрики
- **Database latency** - время запросов к Cassandra
- **Memory usage** - потребление RAM
- **CPU utilization** - загрузка процессора
- **Network I/O** - сетевой трафик

---

## 🧪 Тестирование и профилирование

### 🚀 Нагрузочное тестирование (Locust)

**Реалистичные сценарии пользователей:**
```python
# Автоматические сценарии включают:
1. Регистрацию пользователей (уникальные данные)
2. JWT аутентификацию и получение токенов
3. Просмотр товаров по категориям (с пагинацией)
4. Добавление товаров в корзину (с валидацией)
5. Управление корзиной (обновление, удаление)
6. Оформление заказов (full checkout flow)
7. Мониторинг статусов заказов
8. Агрегацию пользовательских профилей
```

**Веса задач:**
- `browse_products`: 10 (основная активность)
- `manage_cart`: 5 (средняя активность)  
- `place_order`: 1 (редкая активность)

### ⚡ Профилирование производительности

**Автоматическое профилирование:**
- **Декораторы** на ключевых эндпоинтах
- **cProfile** интеграция
- **Snakeviz** совместимые файлы
- **HTTP эндпоинты** для загрузки профилей

**Доступные профили:**
```bash
# Доступ к профилям производительности
http://localhost/profiles/

# Основные профилируемые операции:
- get_products (Backend)
- add_to_cart (Cart Service)  
- create_order (Order Service)
- get_user_profile (User Service)
```

### 📊 Целевые показатели производительности
- **Throughput**: 500+ RPS на сервис
- **P99 latency**: < 500ms для критичных операций
- **P95 latency**: < 200ms для обычных операций
- **Availability**: 99.9% uptime (8.76 hours downtime/year)
- **Database response**: < 100ms для простых запросов
- **Error rate**: < 0.1% для production traffic

---

## 🔧 Технический стек

### 🏗️ Основные технологии
- **Python 3.11** - современная версия с последними оптимизациями
- **FastAPI** - современный async веб-фреймворк для всех сервисов  
- **Apache Cassandra 4.1** - NoSQL база данных для высокой производительности
- **Nginx** - reverse proxy, load balancer и API gateway
- **Docker** - контейнеризация всех компонентов

### 📊 Мониторинг и observability
- **Prometheus** - центральный сбор метрик
- **Grafana** - визуализация и дашборды
- **Jaeger** - распределенный трейсинг
- **Alertmanager** - управление алертами
- **MCAC Agent** - детальный мониторинг Cassandra

### 🧪 Тестирование и развертывание
- **Locust** - нагрузочное тестирование с реалистичными сценариями
- **Docker Compose** - оркестрация всех сервисов
- **Health checks** - мониторинг состояния сервисов
- **Graceful shutdown** - корректное завершение работы

### 🔐 Безопасность
- **JWT токены** - stateless аутентификация
- **bcrypt** - хэширование паролей
- **CORS middleware** - кросс-доменные запросы
- **Role-based access** - разграничение доступа admin/user

---

## 📚 Документация

### 📖 Основные разделы
- **[🏗️ Архитектура системы](architecture.md)** - детальное описание архитектуры, компонентов и взаимодействий
- **[🛍️ Микросервисы](microservices.md)** - техническая документация по каждому сервису с API и примерами
- **[🗄️ База данных](database.md)** - схема данных Cassandra, операции и оптимизация
- **[📊 Мониторинг](monitoring.md)** - система observability, метрики, дашборды и алерты
- **[🔐 Аутентификация](authentication.md)** - JWT токены, безопасность и авторизация
- **[🧪 Тестирование](testing.md)** - руководство по тестированию, Locust сценарии
- **[🚀 Планы развития](future_plans.md)** - roadmap, будущие возможности и улучшения

### 📋 Дополнительные руководства
- **[🔧 Развертывание](reproduce_alerts.md)** - как воспроизвести алерты и тестировать систему
- **[📈 Нагрузочное тестирование](load_testing.md)** - подробное руководство по Locust
- **[🗄️ Обслуживание Cassandra](../CASSANDRA_MAINTENANCE.md)** - администрирование базы данных
- **[⚡ Профилирование](../PROFILING.md)** - анализ производительности кода

---

## 💡 Особенности реализации

### 🔄 Асинхронная архитектура
- **Полностью async** - все межсервисные вызовы используют httpx AsyncClient
- **Non-blocking I/O** - максимальная пропускная способность
- **Background tasks** - асинхронная обработка заказов и уведомлений
- **Connection pooling** - эффективное использование ресурсов

### 🛡️ Отказоустойчивость
- **Health checks** для всех сервисов с timeout и retry
- **Graceful shutdown** с корректной обработкой SIGTERM
- **Circuit breaker patterns** для внешних зависимостей
- **Automatic retry logic** с exponential backoff
- **Resource limits** для предотвращения memory leaks

### 📈 Масштабируемость
- **Stateless сервисы** - готовность к горизонтальному масштабированию
- **Партиционирование данных** в Cassandra по UUID
- **Load balancing** через Nginx с round-robin
- **Container-ready** архитектура с Docker
- **Независимые lifecycle** сервисов

### 🔍 Observability
- **Metrics everywhere** - автоматические и custom метрики
- **Distributed tracing** - полная видимость межсервисных вызовов
- **Structured logging** - консистентное логирование
- **Performance profiling** - детальный анализ производительности

