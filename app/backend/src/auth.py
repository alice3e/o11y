"""
Модуль аутентификации для Backend API
"""
import os
from jose import JWTError, jwt
from fastapi import HTTPException, Header, status
from typing import Optional

# Настройки JWT
SECRET_KEY = os.environ.get("SECRET_KEY", "supersecretkey123")
ALGORITHM = "HS256"


async def get_user_info(authorization: Optional[str] = Header(None)):
    """
    Извлекает информацию о пользователе из JWT токена.
    Возвращает словарь с username и is_admin, или None если токен отсутствует.
    """
    if not authorization:
        return None
    
    # Проверяем формат заголовка
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    
    token = parts[1]
    
    try:
        # Декодируем JWT токен
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            return None
        
        # Получаем информацию о роли из токена или определяем по username
        is_admin = payload.get("is_admin", False) or username.startswith("admin_") or username == "swagger_admin"
        
        return {
            "username": username,
            "is_admin": is_admin
        }
    except JWTError:
        return None


async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Обязательная аутентификация. Возвращает информацию о пользователе или поднимает 401.
    """
    user_info = await get_user_info(authorization)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user_info


async def get_admin_user(authorization: Optional[str] = Header(None)):
    """
    Проверяет, что пользователь является администратором.
    """
    user_info = await get_current_user(authorization)
    if not user_info.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user_info
