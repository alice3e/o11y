# 🚀 Анализ Ansible конфигурации для развертывания Product Store

## 📊 Общий обзор текущей конфигурации

### 🏗️ Структура проекта
```
infra/ansible/
├── ansible.cfg                    # ❌ ПУСТОЙ - нужна конфигурация
├── playbook.yml                   # ✅ Базовая структура есть
├── inventory/
│   └── hosts                      # ⚠️ Требует настройки IP-адреса
├── group_vars/
│   └── all/
│       └── vault.yml              # ✅ Зашифрованные секреты
└── roles/
    ├── common/                    # ✅ Системные пакеты
    ├── docker/                    # ✅ Установка Docker
    └── deploy_app/                # ⚠️ Требует доработки
        └── tasks/
            ├── main.yml
            └── vars/main.yml
```

---

## ✅ Что работает хорошо

### 1. **🔧 Роль Common**
```yaml
# ✅ Правильно обновляет пакеты
- name: Update apt cache
  ansible.builtin.apt:
    update_cache: yes
    cache_valid_time: 3600
    
# ✅ Устанавливает необходимые системные пакеты
- name: Install required system packages
  ansible.builtin.package:
    name: [apt-transport-https, ca-certificates, curl, ...]
```

### 2. **🐳 Роль Docker**
```yaml
# ✅ Корректная установка Docker с официального репозитория
- name: Add Docker GPG key
- name: Add Docker repository  
- name: Install Docker packages
- name: Add remote user to docker group  # ✅ Безопасность
```

### 3. **🔐 Ansible Vault**
- ✅ Секреты зашифрованы в `vault.yml`
- ✅ Правильные права доступа `0600` для токена

---

## ⚠️ Критические проблемы и решения

### 1. **📝 Отсутствует ansible.cfg**

**Проблема**: Пустой файл конфигурации
**Решение**: Создать базовую конфигурацию

```ini
# ansible.cfg
[defaults]
host_key_checking = False
inventory = inventory/hosts
remote_user = yc-user
private_key_file = ~/.ssh/id_rsa
stdout_callback = yaml
retry_files_enabled = False
gathering = smart
fact_caching = memory

[ssh_connection]
ssh_args = -o ControlMaster=auto -o ControlPersist=60s -o UserKnownHostsFile=/dev/null
pipelining = True
control_path = /tmp/ansible-ssh-%%h-%%p-%%r
```

### 2. **🏠 Inventory требует настройки**

**Проблема**: Placeholder для IP-адреса
**Текущий код**:
```ini
[servers]
your_server_ip ansible_user=yc-user
```

**Решение**: Добавить группы и переменные
```ini
# inventory/hosts
[web_servers]
prod-web-01 ansible_host=10.0.1.10 ansible_user=yc-user
prod-web-02 ansible_host=10.0.1.11 ansible_user=yc-user

[db_servers]  
prod-db-01 ansible_host=10.0.1.20 ansible_user=yc-user

[monitoring_servers]
prod-monitor-01 ansible_host=10.0.1.30 ansible_user=yc-user

[all:vars]
# Global variables
ansible_ssh_common_args='-o StrictHostKeyChecking=no'
```

### 3. **🐳 Проблемы с Docker Build**

**Проблема**: Неправильная логика build-а образов
**Текущий код**:
```yaml
- name: Build custom docker images
  community.docker.docker_image:
    name: "{{ item.name }}:latest"
    build:
      path: "{{ item.path.rsplit('/', 1)[0] if 'Dockerfile' in item.path else item.path }}"
```

**Проблемы**:
- ❌ Сложная логика с `rsplit`
- ❌ Не учитывает Docker Build Context
- ❌ Нет проверки успешности build

**Решение**: Упростить и исправить
```yaml
- name: Build application docker images
  community.docker.docker_image:
    name: "{{ item.name }}:{{ app_version | default('latest') }}"
    build:
      path: "{{ project_dest_path }}/{{ item.dockerfile_dir }}"
      dockerfile: "{{ item.dockerfile | default('Dockerfile') }}"
      pull: yes
      buildargs: "{{ item.build_args | default({}) }}"
    source: build
    state: present
    force_source: yes
  with_items: "{{ services_to_build }}"
  register: build_results
  failed_when: build_results.failed == true

# Исправленная переменная services_to_build
services_to_build:
  - name: "backend"
    dockerfile_dir: "app/backend"
    build_args:
      SERVICE_NAME: backend
  - name: "cart-service"
    dockerfile_dir: "app/cart-service"
  - name: "order-service" 
    dockerfile_dir: "app/order-service"
  - name: "user-service"
    dockerfile_dir: "app/user-service"
  - name: "nginx"
    dockerfile_dir: "app/nginx"
  - name: "cassandra"
    dockerfile_dir: "infra/cassandra"
  - name: "alertmanager"
    dockerfile_dir: "infra/alertmanager"
  - name: "locust"
    dockerfile_dir: "infra"
    dockerfile: "locust.Dockerfile"
```

### 4. **📂 Проблемы с Synchronize**

**Проблема**: Слишком агрессивная синхронизация
**Текущий код**:
```yaml
- name: Synchronize project files to the server
  ansible.posix.synchronize:
    src: ../../../ # Копируем все из корневой директории проекта
    dest: "{{ project_dest_path }}"
    archive: yes
    delete: yes # ❌ Опасно - удаляет файлы на сервере
```

**Решение**: Безопасная синхронизация
```yaml
- name: Create project directories
  ansible.builtin.file:
    path: "{{ project_dest_path }}/{{ item }}"
    state: directory
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: '0755'
  loop:
    - app
    - infra
    - scripts

- name: Sync application files (selective)
  ansible.posix.synchronize:
    src: "../../../{{ item }}/"
    dest: "{{ project_dest_path }}/{{ item }}/"
    archive: yes
    checksum: yes
    recursive: yes
    delete: no  # ✅ Безопасно
    rsync_opts:
      - "--exclude=__pycache__"
      - "--exclude=*.pyc"
      - "--exclude=.git"
      - "--exclude=*.log"
      - "--exclude=node_modules"
  loop:
    - app
    - infra
    - scripts
  notify: restart_services
```

---

## 🚀 Рекомендуемые улучшения

### 1. **📋 Добавить Pre-deployment Checks**

```yaml
# roles/common/tasks/pre_checks.yml
- name: Check system requirements
  block:
    - name: Verify minimum RAM
      ansible.builtin.fail:
        msg: "Insufficient RAM. Required: 4GB, Available: {{ ansible_memtotal_mb }}MB"
      when: ansible_memtotal_mb < 4096

    - name: Verify disk space
      ansible.builtin.fail:
        msg: "Insufficient disk space in /opt"
      when: ansible_mounts | selectattr('mount', 'equalto', '/') | map(attribute='size_available') | first < 10737418240  # 10GB

    - name: Check if ports are available
      ansible.builtin.wait_for:
        port: "{{ item }}"
        state: stopped
        timeout: 5
      loop: [80, 443, 9090, 3000, 16686]
      ignore_errors: yes
      register: port_check

    - name: Fail if ports are in use
      ansible.builtin.fail:
        msg: "Port {{ item.item }} is already in use"
      when: item.failed == false
      loop: "{{ port_check.results }}"
```

### 2. **🔄 Добавить Handlers для перезапуска**

```yaml
# roles/deploy_app/handlers/main.yml
- name: restart_services
  community.docker.docker_compose:
    project_src: "{{ project_dest_path }}/infra"
    state: present
    restarted: yes

- name: reload_nginx
  community.docker.docker_container:
    name: nginx
    restart: yes
  
- name: restart_monitoring
  community.docker.docker_compose:
    project_src: "{{ project_dest_path }}/infra"
    services:
      - prometheus
      - grafana
      - alertmanager
    state: present
    restarted: yes
```

### 3. **🏥 Health Checks и валидация**

```yaml
# roles/deploy_app/tasks/health_checks.yml
- name: Wait for services to be healthy
  ansible.builtin.uri:
    url: "http://{{ ansible_default_ipv4.address }}:{{ item.port }}{{ item.path }}"
    method: GET
    status_code: 200
  register: health_check
  until: health_check.status == 200
  retries: 30
  delay: 10
  loop:
    - { port: 8000, path: "/health" }      # Backend
    - { port: 8001, path: "/health" }      # Cart
    - { port: 8002, path: "/health" }      # Order
    - { port: 8003, path: "/health" }      # User
    - { port: 80, path: "/health" }        # Nginx
    - { port: 9090, path: "/-/healthy" }   # Prometheus
    - { port: 3000, path: "/api/health" }  # Grafana

- name: Verify Cassandra is accessible
  ansible.builtin.shell: |
    docker exec cassandra cqlsh -e "DESCRIBE KEYSPACES;"
  register: cassandra_check
  failed_when: "'store' not in cassandra_check.stdout"

- name: Verify Jaeger is collecting traces
  ansible.builtin.uri:
    url: "http://{{ ansible_default_ipv4.address }}:16686/api/services"
    method: GET
  register: jaeger_services
  failed_when: "jaeger_services.json | length == 0"
```

### 4. **🔐 Улучшенная безопасность**

```yaml
# roles/security/tasks/main.yml
- name: Configure firewall rules
  ansible.builtin.ufw:
    rule: allow
    port: "{{ item }}"
    proto: tcp
  loop:
    - 22     # SSH
    - 80     # HTTP
    - 443    # HTTPS
    - 9090   # Prometheus (только для мониторинга)
    - 3000   # Grafana (только для мониторинга)

- name: Block direct access to application ports
  ansible.builtin.ufw:
    rule: deny
    port: "{{ item }}"
    proto: tcp
  loop:
    - 8000   # Backend (через Nginx)
    - 8001   # Cart (через Nginx)
    - 8002   # Order (через Nginx)
    - 8003   # User (через Nginx)

- name: Enable UFW
  ansible.builtin.ufw:
    state: enabled

- name: Set up log rotation for Docker
  ansible.builtin.copy:
    content: |
      /var/lib/docker/containers/*/*.log {
        rotate 7
        daily
        compress
        missingok
        delaycompress
        copytruncate
      }
    dest: /etc/logrotate.d/docker
```

### 5. **📊 Мониторинг развертывания**

```yaml
# roles/deploy_app/tasks/monitoring.yml
- name: Install monitoring tools
  ansible.builtin.package:
    name:
      - htop
      - iotop
      - netstat-nat
      - tcpdump
    state: present

- name: Create monitoring script
  ansible.builtin.copy:
    content: |
      #!/bin/bash
      echo "=== System Resources ==="
      free -h
      df -h
      echo "=== Docker Containers ==="
      docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
      echo "=== Service Health ==="
      curl -s http://localhost/health | jq .
    dest: "{{ project_dest_path }}/scripts/health_check.sh"
    mode: '0755'

- name: Set up log aggregation
  ansible.builtin.copy:
    content: |
      version: '3.8'
      services:
        # Добавить в docker-compose.yml
        filebeat:
          image: elastic/filebeat:8.8.0
          volumes:
            - /var/lib/docker/containers:/var/lib/docker/containers:ro
            - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
          depends_on:
            - elasticsearch
    dest: "{{ project_dest_path }}/infra/logging.yml"
```

---

## 🎯 Финальная структура Playbook

### Улучшенный `playbook.yml`:
```yaml
---
- name: Deploy Product Store Microservices
  hosts: all
  become: yes
  gather_facts: yes
  
  vars:
    app_version: "{{ lookup('env', 'APP_VERSION') | default('latest') }}"
    deployment_env: "{{ lookup('env', 'DEPLOY_ENV') | default('production') }}"
  
  pre_tasks:
    - name: Validate deployment environment
      ansible.builtin.fail:
        msg: "DEPLOY_ENV must be set (development/staging/production)"
      when: deployment_env not in ['development', 'staging', 'production']

  roles:
    - role: common
      tags: [system, common]
    
    - role: security
      tags: [security]
      when: deployment_env == 'production'
    
    - role: docker
      tags: [docker]
    
    - role: deploy_app
      tags: [deploy, app]
  
  post_tasks:
    - name: Run final health checks
      include_tasks: roles/deploy_app/tasks/health_checks.yml
      tags: [health, verify]
    
    - name: Display deployment summary
      ansible.builtin.debug:
        msg: |
          🎉 Deployment completed successfully!
          
          📊 Access URLs:
          - Application: http://{{ ansible_default_ipv4.address }}
          - Prometheus: http://{{ ansible_default_ipv4.address }}:9090
          - Grafana: http://{{ ansible_default_ipv4.address }}:3000
          - Jaeger: http://{{ ansible_default_ipv4.address }}:16686
          
          🔧 Management:
          - SSH: ssh {{ ansible_user }}@{{ ansible_default_ipv4.address }}
          - Logs: docker-compose -f {{ project_dest_path }}/infra/docker-compose.yml logs
          - Health: {{ project_dest_path }}/scripts/health_check.sh
```

---

## 🚀 Команды для развертывания

### 1. **🔐 Подготовка секретов**
```bash
# Создание Ansible Vault
ansible-vault create group_vars/all/vault.yml

# Добавить в vault:
alertmanager_bot_token: "YOUR_TELEGRAM_BOT_TOKEN"
grafana_admin_password: "secure_password_123"
cassandra_password: "cassandra_secure_pass"
```

### 2. **📋 Проверка конфигурации**
```bash
# Синтаксис
ansible-playbook --syntax-check playbook.yml

# Dry run
ansible-playbook --check playbook.yml --ask-vault-pass

# Только определенные теги
ansible-playbook playbook.yml --tags "common,docker" --ask-vault-pass
```

### 3. **🚀 Развертывание**
```bash
# Полное развертывание
ansible-playbook playbook.yml --ask-vault-pass

# Только обновление приложения
ansible-playbook playbook.yml --tags "deploy" --ask-vault-pass

# С debug выводом
ansible-playbook playbook.yml --ask-vault-pass -vvv
```

### 4. **🔍 Проверка после развертывания**
```bash
# Подключение к серверу
ssh yc-user@YOUR_SERVER_IP

# Проверка статуса контейнеров
cd /opt/microservices-app/infra
docker-compose ps

# Проверка логов
docker-compose logs -f --tail=100

# Health check скрипт
./scripts/health_check.sh
```

---

## 📝 Рекомендации по использованию

### 1. **🔄 CI/CD Integration**
```yaml
# .github/workflows/deploy.yml
name: Deploy to Production
on:
  push:
    branches: [main]
    
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy with Ansible
        env:
          ANSIBLE_VAULT_PASSWORD: ${{ secrets.ANSIBLE_VAULT_PASSWORD }}
        run: |
          echo "$ANSIBLE_VAULT_PASSWORD" > vault_pass.txt
          ansible-playbook playbook.yml --vault-password-file vault_pass.txt
          rm vault_pass.txt
```

### 2. **🎯 Environment-specific переменные**
```yaml
# group_vars/production.yml
deployment_env: production
app_version: "v1.2.0"
cassandra_heap_size: "2G"
log_level: "INFO"

# group_vars/staging.yml  
deployment_env: staging
app_version: "latest"
cassandra_heap_size: "1G"
log_level: "DEBUG"
```

### 3. **📊 Мониторинг развертывания**
- ✅ Настроить Grafana Dashboard для мониторинга развертывания
- ✅ Добавить Slack/Telegram уведомления о статусе
- ✅ Использовать Ansible Callback Plugins для логирования

---

## 🎉 Заключение

**Текущая Ansible конфигурация** имеет хорошую базовую структуру, но требует существенных доработок для production-ready развертывания.

**Основные проблемы**:
- ❌ Отсутствует `ansible.cfg`
- ❌ Неправильная логика Docker build
- ❌ Отсутствуют health checks
- ❌ Небезопасная синхронизация файлов

**После исправлений получим**:
- ✅ Production-ready развертывание
- ✅ Proper error handling и rollback
- ✅ Comprehensive health checks
- ✅ Security best practices
- ✅ Monitoring и logging integration
