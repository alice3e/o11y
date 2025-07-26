# Простая настройка Alertmanager для Telegram

## Быстрый старт

### 1. Создайте Telegram бота
1. Найдите @BotFather в Telegram
2. Выполните `/newbot` и следуйте инструкциям
3. Сохраните токен бота

### 2. Создайте публичный канал
1. Создайте публичный канал в Telegram
2. Добавьте бота как администратора
3. Запомните название канала (например: `@my_alerts_channel`)

### 3. Настройте переменные
```bash
cp infra/alertmanager/.env.example infra/alertmanager/.env
```

Отредактируйте `.env`:
```env
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TELEGRAM_CHANNEL_ID=@ваш_публичный_канал
```

### 4. Запустите
```bash
cd infra
docker-compose up -d alertmanager prometheus
```

### 5. Проверьте
```bash
./alertmanager/test_alerts.sh
```

## Настроенные алерты

1. **Высокое время ответа P99 > 500ms** для эндпоинтов:
   - `/api/products/?category=[category]`
   - `/api/products/[product_id]`
   - `/cart-api/cart/items (add)`
   - `/user-api/users/me/orders (checkout)`

2. **RPS в БД > 100 запросов/сек**

## Полезные ссылки
- Alertmanager UI: http://localhost:9093
- Prometheus Alerts: http://localhost:9090/alerts
