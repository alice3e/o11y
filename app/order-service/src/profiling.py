import os
import cProfile
import pstats
import sys
from contextlib import contextmanager
from datetime import datetime
import logging
from functools import wraps
from io import StringIO

logger = logging.getLogger(__name__)

ENABLE_PROFILING = os.environ.get("ENABLE_PROFILING", "false").lower() == "true"
PROFILES_DIR = "/app/profiles"

def ensure_profiles_dir():
    """Создает директорию для профилей если она не существует"""
    if not os.path.exists(PROFILES_DIR):
        os.makedirs(PROFILES_DIR, exist_ok=True)

@contextmanager
def profile_context(profile_name: str):
    """Контекстный менеджер для профилирования блока кода"""
    if not ENABLE_PROFILING:
        yield
        return
    
    ensure_profiles_dir()
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    try:
        yield profiler
    finally:
        profiler.disable()
        
        # Сохраняем профиль
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"order-service_{profile_name}_{timestamp}.prof"
        filepath = os.path.join(PROFILES_DIR, filename)
        
        profiler.dump_stats(filepath)
        logger.info(f"Profile saved to {filepath}")

def profile_endpoint(endpoint_name: str):
    """Декоратор для профилирования эндпоинтов"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not ENABLE_PROFILING:
                return await func(*args, **kwargs)
            
            with profile_context(f"endpoint_{endpoint_name}"):
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def get_profile_stats(profile_path: str) -> str:
    """Получает текстовую статистику профиля"""
    if not os.path.exists(profile_path):
        return "Profile not found"
    
    try:
        # Перенаправляем stdout во временный буфер
        old_stdout = sys.stdout
        sys.stdout = buffer = StringIO()
        
        stats = pstats.Stats(profile_path)
        stats.print_stats()
        
        # Возвращаем stdout обратно
        sys.stdout = old_stdout
        
        return buffer.getvalue()
    except Exception as e:
        return f"Error reading profile: {str(e)}"

def list_available_profiles() -> list:
    """Возвращает список доступных профилей для order-service"""
    if not os.path.exists(PROFILES_DIR):
        return []
    
    profiles = []
    for filename in os.listdir(PROFILES_DIR):
        if filename.endswith('.prof') and 'order-service' in filename:
            filepath = os.path.join(PROFILES_DIR, filename)
            stat = os.stat(filepath)
            profiles.append({
                'filename': filename,
                'service': 'order-service',
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    
    return sorted(profiles, key=lambda x: x['modified'], reverse=True)
