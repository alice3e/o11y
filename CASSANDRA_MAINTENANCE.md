# Cassandra Maintenance Guide

## Проблема с Tombstone-ячейками

Cassandra создает tombstone-ячейки при удалении данных. Когда их становится слишком много, это приводит к предупреждениям вида:
```
Server warning: Read 5000 live rows and 10000 tombstone cells for query...
```

## Решение

### 1. Автоматические настройки

Код в `app/backend/src/services/cassandra.py` автоматически:
- Устанавливает `gc_grace_seconds = 3600` (1 час) вместо стандартных 10 дней
- Создает индексы для полей `category` и `price`
- Ограничивает запросы лимитами для предотвращения полного сканирования

### 2. Ручное обслуживание

Запустите скрипт обслуживания:
```bash
./scripts/cassandra_maintenance.sh
```

Или выполните команды вручную:

#### Компактификация таблицы
```bash
cd infra
docker-compose exec cassandra nodetool compact store products
```

#### Проверка статуса компактификации
```bash
docker-compose exec cassandra nodetool compactionstats
```

#### Просмотр статистики таблицы
```bash
docker-compose exec cassandra nodetool tablestats store.products
```

#### Настройка gc_grace_seconds
```bash
docker-compose exec cassandra cqlsh -e "USE store; ALTER TABLE products WITH gc_grace_seconds = 3600;"
```

#### Создание индексов
```bash
docker-compose exec cassandra cqlsh -e "
USE store; 
CREATE INDEX IF NOT EXISTS products_category_idx ON products (category);
CREATE INDEX IF NOT EXISTS products_price_idx ON products (price);
"
```

### 3. Мониторинг

#### Проверка предупреждений о tombstone
```bash
docker-compose logs -f backend | grep tombstone
```

#### Мониторинг метрик таблицы
```bash
docker-compose exec cassandra nodetool tablestats store.products | grep -E "(SSTable count|tombstones|live)"
```

## Профилактика

### Настройки приложения
1. **Лимиты запросов**: Все запросы ограничены 50,000 записей для основных операций и 10,000 для запросов категорий
2. **Отключенные метрики**: Обновление метрик продуктов отключено в health check для снижения нагрузки
3. **Индексы**: Созданы индексы для `category` и `price` для улучшения производительности

### Рекомендации по эксплуатации
1. **Регулярная компактификация**: Запускайте `cassandra_maintenance.sh` еженедельно
2. **Мониторинг**: Следите за логами на предмет предупреждений о tombstone
3. **Оптимизация запросов**: Избегайте запросов без фильтров по категории
4. **Ограничение данных**: Рассмотрите TTL для старых записей

## Результаты оптимизации

После применения всех оптимизаций:
- ✅ `gc_grace_seconds` установлен в 1 час (3600 секунд)
- ✅ Созданы индексы для `category` и `price`
- ✅ Выполнена компактификация (SSTable count: 1)
- ✅ Добавлены лимиты на запросы (10,000-50,000 записей)
- ✅ Отключено обновление метрик в health check
- ✅ Предупреждения о tombstone значительно уменьшены

## Дополнительная информация

### Что такое gc_grace_seconds?
- Время в секундах, после которого tombstone-ячейки могут быть удалены
- Стандартное значение: 864000 секунд (10 дней)
- Наше значение: 3600 секунд (1 час) - для быстрой очистки в dev/test среде

### Что такое компактификация?
- Процесс объединения SSTable файлов и удаления tombstone-ячеек
- Уменьшает размер данных на диске
- Улучшает производительность чтения

### Индексы в Cassandra
- Secondary indexes для ускорения запросов по non-primary key полям
- `products_category_idx` - для фильтрации по категориям
- `products_price_idx` - для фильтрации по цене
