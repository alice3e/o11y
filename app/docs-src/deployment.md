# 🚀 Production Deployment Guide

Полное руководство по развертыванию Product Store в production среде с использованием Docker и Docker Compose.

## 📋 Архитектура развертывания

### 🏗️ Компоненты системы
```
Production Environment
├── 🌐 Nginx (Reverse Proxy/Load Balancer)
├── 🏪 Backend Service (Product API)  
├── 🛒 Cart Service (Shopping Cart)
├── 📦 Order Service (Order Processing)
├── 👤 User Service (Authentication)
├── 🗄️ Cassandra (Database)
├── 📊 Prometheus (Metrics Collection)
├── 📈 Grafana (Monitoring Dashboard)
├── 🔍 Jaeger (Distributed Tracing)
└── 🚨 Alertmanager (Alert Management)
```

### 🌍 Network Architecture
```
Internet → Nginx:80 → Microservices:8000-8003
                   → Prometheus:9090
                   → Grafana:3000
                   → Jaeger:16686
```

## 🛠️ Системные требования

### ⚙️ Минимальные требования
- **OS**: Ubuntu 20.04+ / CentOS 8+ / RHEL 8+
- **RAM**: 4GB (рекомендуется 8GB)
- **CPU**: 2 cores (рекомендуется 4+ cores)  
- **Disk**: 20GB свободного места (рекомендуется 50GB SSD)
- **Network**: открытые порты 80, 443, 22 (SSH)

### 🏢 Production требования
- **RAM**: 8GB+ (рекомендуется 16GB)
- **CPU**: 4+ cores (рекомендуется 8+ cores)
- **Disk**: 50GB+ SSD storage с RAID
- **Network**: 1Gbps, низкая latency
- **Monitoring**: внешний мониторинг availability

## 🚀 Пошаговое развертывание

### 1. **🔧 Подготовка сервера**

#### Обновление системы
```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL
sudo yum update -y
```

#### Установка Docker
```bash
# Установка Docker Engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER

# Перезапуск сессии для применения изменений
newgrp docker
```

#### Установка Docker Compose
```bash
# Установка последней версии Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Добавление прав на выполнение
sudo chmod +x /usr/local/bin/docker-compose

# Проверка установки
docker-compose --version
```

### 2. **📥 Клонирование проекта**

```bash
# Создание директории для проекта
sudo mkdir -p /opt/microservices-app
sudo chown -R $USER:$USER /opt/microservices-app

# Клонирование репозитория
cd /opt
git clone <repository-url> microservices-app
cd microservices-app
```

### 3. **🔐 Настройка переменных окружения**

#### Создание production конфигурации
```bash
# Копирование примера конфигурации
cp infra/.env.example infra/.env.production

# Редактирование для production
nano infra/.env.production
```

#### Production переменные
```env
# === ОСНОВНЫЕ НАСТРОЙКИ ===
ENVIRONMENT=production
DEBUG=false

# === БЕЗОПАСНОСТЬ ===
# Генерируем случайный JWT ключ
JWT_SECRET_KEY=SuperSecretProductionJWTKey123456789
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=30

# === БАЗЫ ДАННЫХ ===
CASSANDRA_HOST=cassandra
CASSANDRA_PORT=9042
CASSANDRA_KEYSPACE=product_store
CASSANDRA_PASSWORD=SecureCassandraPass123!

# === МОНИТОРИНГ ===
PROMETHEUS_HOST=prometheus
PROMETHEUS_PORT=9090
GRAFANA_ADMIN_PASSWORD=SecureGrafanaPass123!

# === АЛЕРТЫ ===
# Получить у @BotFather в Telegram
TELEGRAM_BOT_TOKEN=1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
TELEGRAM_CHAT_ID=-100123456789

# === TRACING ===
JAEGER_ENDPOINT=http://jaeger:14268/api/traces
JAEGER_AGENT_HOST=jaeger
JAEGER_AGENT_PORT=6831

# === NGINX ===
NGINX_PORT=80
NGINX_SSL_PORT=443
```

### 4. **🚀 Запуск системы**

#### Создание Docker сетей
```bash
cd /opt/microservices-app/infra

# Создание custom network для лучшей изоляции
docker network create microservices-network || true
```

#### Запуск всех сервисов
```bash
# Production запуск с custom env файлом
docker-compose --env-file .env.production up -d

# Проверка статуса всех сервисов
docker-compose ps
```

#### Мониторинг запуска
```bash
# Просмотр логов всех сервисов
docker-compose logs -f --tail=50

# Логи конкретного сервиса
docker-compose logs -f backend
docker-compose logs -f cassandra
docker-compose logs -f nginx
```

### 5. **✅ Проверка развертывания**

#### Health Check скрипт
```bash
#!/bin/bash
# health_check.sh

echo "🔍 Проверка состояния сервисов..."

services=(
  "http://localhost/health:Nginx+Backend"
  "http://localhost:9090/-/healthy:Prometheus" 
  "http://localhost:3000/api/health:Grafana"
  "http://localhost:16686/api/services:Jaeger"
)

for service in "${services[@]}"; do
  url="${service%:*}"
  name="${service#*:}"
  
  if curl -s -f "$url" > /dev/null; then
    echo "✅ $name - OK"
  else
    echo "❌ $name - FAILED"
    exit 1
  fi
done

echo "🎉 Все сервисы работают!"
```

#### Запуск проверки
```bash
chmod +x scripts/health_check.sh
./scripts/health_check.sh
```

### 6. **🔒 SSL/TLS настройка (опционально)**

#### Установка Certbot
```bash
# Ubuntu/Debian
sudo apt install certbot python3-certbot-nginx -y

# CentOS/RHEL  
sudo yum install certbot python3-certbot-nginx -y
```

#### Получение SSL сертификата
```bash
# Замените yourdomain.com на ваш домен
sudo certbot --nginx -d yourdomain.com

# Автоматическое обновление
sudo crontab -e
# Добавить: 0 12 * * * /usr/bin/certbot renew --quiet
```

## 🔧 Управление системой

### 📊 Основные команды Docker Compose

#### Управление сервисами
```bash
cd /opt/microservices-app/infra

# Остановка всех сервисов
docker-compose stop

# Запуск остановленных сервисов  
docker-compose start

# Перезапуск всех сервисов
docker-compose restart

# Перезапуск конкретного сервиса
docker-compose restart backend
docker-compose restart nginx

# Полная остановка и удаление
docker-compose down
```

#### Просмотр логов
```bash
# Логи всех сервисов
docker-compose logs -f --tail=100

# Логи конкретного сервиса
docker-compose logs -f backend --tail=50
docker-compose logs -f cassandra --since=10m

# Поиск в логах
docker-compose logs backend | grep "ERROR"
```

#### Мониторинг ресурсов
```bash
# Использование ресурсов контейнерами
docker stats

# Подробная информация о контейнере
docker inspect microservices_backend_1

# Проверка сетей
docker network ls
docker network inspect microservices_default
```

### 🔄 Обновление приложения

#### Плавное обновление (Zero Downtime)
```bash
cd /opt/microservices-app

# 1. Получение новой версии
git fetch origin
git checkout main  # или нужная ветка
git pull origin main

# 2. Обновление только приложения
cd infra
docker-compose --env-file .env.production pull backend cart-service order-service user-service

# 3. Поочередное обновление сервисов
for service in backend cart-service order-service user-service; do
  echo "Обновление $service..."
  docker-compose --env-file .env.production up -d --no-deps $service
  sleep 10  # Ждем запуска
  
  # Проверка health check
  if ! curl -f http://localhost/health; then
    echo "❌ Ошибка при обновлении $service"
    exit 1
  fi
  echo "✅ $service обновлен"
done

echo "🎉 Все сервисы обновлены!"
```

#### Откат к предыдущей версии
```bash
# Откат Git
git log --oneline -5  # Смотрим последние коммиты
git checkout <previous-commit-hash>

# Пересборка и запуск
docker-compose --env-file .env.production up -d --build
```

### 🧹 Обслуживание системы

#### Очистка ресурсов Docker
```bash
# Очистка неиспользуемых образов
docker image prune -f

# Очистка неиспользуемых контейнеров
docker container prune -f

# Очистка неиспользуемых сетей
docker network prune -f

# Очистка неиспользуемых volumes
docker volume prune -f

# Полная очистка системы
docker system prune -a -f
```

#### Backup и восстановление
```bash
# Backup конфигурации
sudo tar -czf /backup/microservices-config-$(date +%Y%m%d).tar.gz /opt/microservices-app/

# Backup данных Cassandra
docker-compose exec cassandra nodetool snapshot

# Backup Grafana dashboards
docker-compose exec grafana grafana-cli admin export-dashboard

# Backup Prometheus data
sudo tar -czf /backup/prometheus-data-$(date +%Y%m%d).tar.gz /opt/microservices-app/infra/prometheus/data/
```

## 🚨 Мониторинг и алерты

### 📈 Grafana Dashboard

#### Доступ к Grafana
- **URL**: http://your-server-ip:3000
- **Логин**: admin  
- **Пароль**: из .env.production (GRAFANA_ADMIN_PASSWORD)

#### Основные дашборды
- **System Overview**: общее состояние системы
- **Backend Metrics**: метрики Backend API
- **Cart Service**: метрики корзины
- **Order Service**: метрики заказов
- **User Service**: метрики пользователей
- **Cassandra**: метрики базы данных

### 🔍 Jaeger Tracing

#### Доступ к Jaeger
- **URL**: http://your-server-ip:16686
- **Features**: distributed tracing, performance analysis

#### Полезные запросы
- Поиск по service: `backend`, `cart-service`, `order-service`
- Поиск по operation: `GET /products`, `POST /cart/items`
- Анализ медленных запросов: > 1000ms

### 🚨 Alertmanager

#### Настройка уведомлений
Алерты настроены для отправки в Telegram:
- **High CPU Usage** (>80% в течение 5 минут)
- **High Memory Usage** (>90% в течение 5 минут)
- **Service Down** (недоступность сервиса)
- **High Error Rate** (>5% ошибок в течение 5 минут)

## 🔧 Troubleshooting

### ❌ Часто встречающиеся проблемы

#### 1. Docker Service Failures
```bash
# Проверка статуса
docker-compose ps

# Детальная информация об ошибке
docker-compose logs service-name

# Перезапуск проблемного сервиса
docker-compose restart service-name

# Принудительное пересоздание
docker-compose up -d --force-recreate service-name
```

#### 2. Network Issues
```bash
# Проверка Docker сетей
docker network ls
docker network inspect microservices_default

# Проверка портов
sudo netstat -tlnp | grep -E ":(80|3000|9090|16686)"

# Проверка firewall
sudo ufw status
sudo iptables -L INPUT
```

#### 3. Storage Issues
```bash
# Проверка дискового пространства
df -h

# Проверка inode usage
df -i

# Размер Docker данных
sudo du -sh /var/lib/docker/

# Очистка места
docker system prune -a -f
```

#### 4. Performance Issues
```bash
# Мониторинг ресурсов
htop
iotop
nethogs

# Анализ логов на ошибки
docker-compose logs | grep -i error
docker-compose logs | grep -i warn

# Проверка задержек сети
ping cassandra
nc -zv cassandra 9042
```

#### 5. Cassandra Issues
```bash
# Проверка статуса кластера
docker-compose exec cassandra nodetool status

# Проверка подключения
docker-compose exec cassandra cqlsh -e "DESCRIBE KEYSPACES;"

# Анализ логов Cassandra
docker-compose logs cassandra | grep -i error

# Перезапуск с очисткой данных (ОСТОРОЖНО!)
docker-compose stop cassandra
docker volume rm infra_cassandra_data
docker-compose up -d cassandra
```

### 🆘 Emergency Recovery

#### Быстрое восстановление сервиса
```bash
# 1. Остановка всех сервисов
docker-compose down

# 2. Очистка проблемных данных
docker system prune -f
docker volume prune -f

# 3. Восстановление из backup
cd /backup
tar -xzf microservices-config-latest.tar.gz -C /

# 4. Запуск системы
cd /opt/microservices-app/infra
docker-compose --env-file .env.production up -d

# 5. Проверка
./scripts/health_check.sh
```

## 🔄 CI/CD Integration

### 🤖 GitHub Actions

#### Автоматическое развертывание
```yaml
# .github/workflows/deploy-production.yml
name: Deploy to Production

on:
  push:
    branches: [main]
  workflow_dispatch:  # Ручной запуск

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Setup SSH
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.PRODUCTION_SSH_KEY }}" > ~/.ssh/production-key
          chmod 600 ~/.ssh/production-key
          ssh-keyscan -H ${{ secrets.PRODUCTION_HOST }} >> ~/.ssh/known_hosts
      
      - name: Deploy to production
        env:
          PROD_HOST: ${{ secrets.PRODUCTION_HOST }}
          PROD_USER: ${{ secrets.PRODUCTION_USER }}
        run: |
          ssh -i ~/.ssh/production-key $PROD_USER@$PROD_HOST "
            cd /opt/microservices-app &&
            git pull origin main &&
            cd infra &&
            docker-compose --env-file .env.production pull &&
            docker-compose --env-file .env.production up -d &&
            sleep 30
          "
      
      - name: Verify deployment
        env:
          PROD_HOST: ${{ secrets.PRODUCTION_HOST }}
        run: |
          for i in {1..10}; do
            if curl -f http://$PROD_HOST/health; then
              echo "✅ Deployment successful!"
              exit 0
            fi
            echo "⏳ Waiting for services to start... ($i/10)"
            sleep 30
          done
          echo "❌ Deployment verification failed!"
          exit 1
      
      - name: Notify deployment
        if: always()
        run: |
          # Уведомление в Slack/Telegram о результате деплоя
          echo "Deployment completed with status: ${{ job.status }}"
```

#### Required GitHub Secrets
```bash
# Настройка секретов в GitHub
PRODUCTION_SSH_KEY=<private-ssh-key-content>
PRODUCTION_HOST=your-server-ip
PRODUCTION_USER=deployment-user
```

### 🔄 Alternative: GitLab CI/CD
```yaml
# .gitlab-ci.yml
stages:
  - test
  - deploy

variables:
  DOCKER_HOST: tcp://docker:2376
  DOCKER_TLS_CERTDIR: "/certs"

deploy_production:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache openssh-client curl
    - mkdir -p ~/.ssh
    - echo "$PRODUCTION_SSH_KEY" > ~/.ssh/id_rsa
    - chmod 600 ~/.ssh/id_rsa
    - ssh-keyscan -H $PRODUCTION_HOST >> ~/.ssh/known_hosts
  script:
    - |
      ssh $PRODUCTION_USER@$PRODUCTION_HOST "
        cd /opt/microservices-app &&
        git pull origin main &&
        cd infra &&
        docker-compose --env-file .env.production up -d
      "
    - sleep 30
    - curl -f http://$PRODUCTION_HOST/health
  only:
    - main
  when: manual
```

## 📊 Production Best Practices

### 🛡️ Security Checklist
- ✅ Все пароли используют strong passwords
- ✅ JWT tokens имеют reasonable expiration
- ✅ SSL/TLS настроен для external connections  
- ✅ Firewall блокирует неиспользуемые порты
- ✅ Docker containers запускаются под non-root users
- ✅ Secrets не хранятся в Git repository
- ✅ Regular security updates применяются

### ⚡ Performance Optimization
- ✅ Docker containers имеют resource limits
- ✅ Nginx gzip compression включен
- ✅ Static files кешируются
- ✅ Database connections pooled
- ✅ Healthchecks настроены с reasonable intervals
- ✅ Log rotation настроен
- ✅ Monitoring alerts настроены

### 🔄 Operational Excellence
- ✅ Automated backups настроены
- ✅ Disaster recovery plan документирован
- ✅ Monitoring covers business metrics
- ✅ Alerting имеет clear escalation paths
- ✅ Documentation актуальна
- ✅ Runbooks созданы для common issues

---

**🚀 Готово!** Ваша Product Store система развернута в production среде с полным мониторингом, алертами и автоматизацией! 

Используйте Grafana дашборды для мониторинга производительности и Jaeger для анализа трассировок запросов.
