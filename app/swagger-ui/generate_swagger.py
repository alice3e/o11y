import json
import requests
import os

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

# Путь для сохранения итогового файла
OUTPUT_FILE = "/usr/share/nginx/html/swagger.json"

# --- Основной скрипт ---
def merge_specs():
    """
    Запрашивает OpenAPI спецификации у всех сервисов,
    объединяет их в одну и сохраняет в файл.
    """
    # Инициализация итоговой спецификации на основе первого сервиса
    first_service_name = list(SERVICES.keys())[0]
    first_service_info = SERVICES[first_service_name]
    
    try:
        response = requests.get(first_service_info["url"])
        response.raise_for_status()
        merged_spec = response.json()
        
        # Обновляем пути с учетом префикса
        merged_spec['paths'] = {
            f"{first_service_info['prefix']}{path}": value
            for path, value in merged_spec.get('paths', {}).items()
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching spec from {first_service_name}: {e}")
        return

    # Обработка остальных сервисов
    for service_name, service_info in list(SERVICES.items())[1:]:
        try:
            response = requests.get(service_info["url"])
            response.raise_for_status()
            spec = response.json()
            
            # Добавляем пути с префиксами
            for path, path_item in spec.get('paths', {}).items():
                merged_spec['paths'][f"{service_info['prefix']}{path}"] = path_item
            
            # Объединяем компоненты (схемы, параметры и т.д.)
            if 'components' in spec:
                for comp_type, comps in spec['components'].items():
                    if comp_type not in merged_spec['components']:
                        merged_spec['components'][comp_type] = {}
                    merged_spec['components'][comp_type].update(comps)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching spec from {service_name}: {e}")
            continue

    # Сохраняем итоговый файл
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(merged_spec, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully merged specs into {OUTPUT_FILE}")

if __name__ == "__main__":
    merge_specs() 