import json
import requests
import os
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Настройки ---
# Словарь, где ключ - это имя сервиса, а значение - его URL и префикс пути
SERVICES = {
    "backend": {
        "url": "http://backend:8000/openapi.json",
        "prefix": "/api"
    },
    "cart-service": {
        "url": "http://cart-service:8001/openapi.json",
        "prefix": "/cart-api"
    },
    "order-service": {
        "url": "http://order-service:8002/openapi.json",
        "prefix": "/order-api"
    },
    "user-service": {
        "url": "http://user-service:8003/openapi.json",
        "prefix": "/user-api"
    }
}

# Максимальное количество попыток получения спецификаций
MAX_RETRIES = 10
# Задержка между попытками в секундах
RETRY_DELAY = 3

# Путь для сохранения итогового файла
OUTPUT_FILE = "/usr/share/nginx/html/swagger.json"

# --- Основной скрипт ---
def merge_specs():
    """
    Запрашивает OpenAPI спецификации у всех сервисов,
    объединяет их в одну и сохраняет в файл.
    """
    # Создадим новую базовую спецификацию
    merged_spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Unified Store API",
            "description": "Объединенный API магазина, включающий все микросервисы",
            "version": "1.0.0"
        },
        "paths": {},
        "components": {
            "schemas": {},
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                },
                "adminAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "admin"
                }
            }
        },
        "security": []
    }
    
    # Собираем все спецификации от сервисов
    for service_name, service_info in SERVICES.items():
        retries = 0
        while retries < MAX_RETRIES:
            try:
                logger.info(f"Fetching OpenAPI spec from {service_name} ({service_info['url']})")
                response = requests.get(service_info["url"], timeout=5)
                response.raise_for_status()
                spec = response.json()
                
                # Добавляем информацию о сервисе в общее описание
                if "info" in spec and "title" in spec["info"]:
                    service_title = spec["info"]["title"]
                    service_description = spec["info"].get("description", "")
                    merged_spec["info"]["description"] += f"\n\n## {service_title}\n{service_description}"
                
                # Обрабатываем пути
                for path, path_item in spec.get('paths', {}).items():
                    # Добавляем префикс к путям
                    prefixed_path = f"{service_info['prefix']}{path}"
                    
                    # Добавляем информацию о сервисе в теги для каждой операции
                    for method, operation in path_item.items():
                        if method not in ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']:
                            continue
                            
                        # Добавляем тег с именем сервиса, если не указано иное
                        if 'tags' not in operation or not operation['tags']:
                            operation['tags'] = [service_name]
                        
                        # Добавляем информацию о требованиях авторизации
                        if "security" not in operation:
                            # Проверяем, есть ли в параметрах Header "Authorization" или есть ли ссылка на зависимость авторизации
                            requires_auth = False
                            requires_admin = False
                            
                            # Проверка на наличие Header параметров
                            for param in operation.get("parameters", []):
                                if param.get("in") == "header" and param.get("name") in ["Authorization", "admin"]:
                                    requires_auth = True
                                    if param.get("name") == "admin":
                                        requires_admin = True
                            
                            # Проверка описания операции на наличие упоминаний о аутентификации
                            description = operation.get("description", "").lower()
                            if "admin" in description:
                                requires_admin = True
                                requires_auth = True
                            elif any(auth_term in description for auth_term in ["auth", "token", "login", "authenticated"]):
                                requires_auth = True
                            
                            # Добавляем схемы безопасности если нужно
                            if requires_auth:
                                security_schemes = []
                                if requires_admin:
                                    security_schemes.append({"adminAuth": []})
                                security_schemes.append({"bearerAuth": []})
                                operation["security"] = security_schemes
                    
                    # Добавляем операцию в объединенную спецификацию
                    merged_spec['paths'][prefixed_path] = path_item
                
                # Объединяем компоненты
                if 'components' in spec:
                    for comp_type, comps in spec['components'].items():
                        if comp_type != "securitySchemes":  # Не перезаписываем наши схемы безопасности
                            if comp_type not in merged_spec['components']:
                                merged_spec['components'][comp_type] = {}
                            # Объединяем с учетом возможных конфликтов имен
                            for comp_name, comp in comps.items():
                                if comp_name in merged_spec['components'][comp_type]:
                                    # В случае конфликта добавляем префикс сервиса
                                    prefix = service_name.replace("-", "_")
                                    new_comp_name = f"{prefix}_{comp_name}"
                                    merged_spec['components'][comp_type][new_comp_name] = comp
                                else:
                                    merged_spec['components'][comp_type][comp_name] = comp
                
                logger.info(f"Successfully fetched spec from {service_name}")
                break  # Успешно получили спецификацию, выходим из цикла повторных попыток
                
            except requests.exceptions.RequestException as e:
                retries += 1
                logger.warning(f"Error fetching spec from {service_name} (attempt {retries}/{MAX_RETRIES}): {e}")
                if retries < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Failed to fetch spec from {service_name} after {MAX_RETRIES} attempts")

    # Сохраняем итоговый файл
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(merged_spec, f, ensure_ascii=False, indent=2)
        
    logger.info(f"Successfully merged specs into {OUTPUT_FILE}")

if __name__ == "__main__":
    merge_specs() 