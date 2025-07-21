# Файл: app/backend/src/core/models.py
import uuid
from decimal import Decimal
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from typing import List

# --- Базовые строительные блоки ---

class ProductCore(BaseModel):
    """
    Самые базовые поля, присущие любому товару.
    """
    name: str = Field(..., example="Молоко 'Простоквашино'")
    category: str = Field(..., example="Молочные продукты")
    price: Decimal = Field(..., gt=0, description="99.90",)

class ProductStock(BaseModel):
    """
    Поля, связанные с остатками на складе.
    """
    stock_count: int = Field(..., ge=0, example=100)

class ProductDescription(BaseModel):
    """
    Опциональные описательные поля.
    """
    description: str | None = Field(None, example="Отборное молоко, 3.2% жирности")
    manufacturer: str | None = Field(None, example="Danone")

# --- Финальные модели для API, собранные из блоков ---

class ProductCreate(ProductCore, ProductStock, ProductDescription):
    """
    Модель для СОЗДАНИЯ товара.
    Собирает в себе все необходимые поля.
    """
    pass  # Все поля унаследованы, своего ничего нет

class ProductOut(ProductCore):
    """
    Модель для отображения товара в СПИСКЕ.
    Включает только основные поля + ID.
    """
    product_id: uuid.UUID

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: lambda v: str(v),
            Decimal: lambda v: float(v),
        }

class ProductDetailsOut(ProductOut, ProductStock, ProductDescription):
    """
    Модель для отображения ПОЛНОЙ информации о товаре.
    Наследует все от ProductOut и добавляет остатки и описание.
    """
    pass # Все поля унаследованы


class ProductUpdate(BaseModel):
    name: str | None = Field(None, example="Молоко 'Домик в деревне'")
    category: str | None = Field(None, example="Молочные продукты")
    price: Decimal | None = Field(None, gt=0, description="109.90")
    stock_count: int | None = Field(None, ge=0, example=50)
    description: str | None = Field(None, example="Отборное коровье молоко, 3.2% жирности")
    manufacturer: str | None = Field(None, example="Вимм-Билль-Данн")

# New model for category listing
class CategoryOut(BaseModel):
    """
    Модель для отображения категории и количества товаров в ней.
    """
    name: str = Field(..., example="Молочные продукты")
    product_count: int = Field(..., ge=0, example=15)

# Models for pagination
class PaginationMetadata(BaseModel):
    """
    Метаданные пагинации
    """
    total: int = Field(..., description="Общее количество элементов")
    page: int = Field(..., description="Текущая страница")
    pages: int = Field(..., description="Общее количество страниц")
    has_next: bool = Field(..., description="Есть ли следующая страница")
    has_prev: bool = Field(..., description="Есть ли предыдущая страница")

class PaginatedProductsResponse(PaginationMetadata):
    """
    Ответ с пагинацией для списка товаров
    """
    items: List[ProductOut] = Field(..., description="Список товаров")

# Models for recent views tracking
class RecentViewedProduct(BaseModel):
    """
    Модель для отслеживания недавно просмотренных товаров
    """
    product_id: UUID
    viewed_at: str = Field(..., description="Время просмотра в ISO формате")

class RecentViewsUpdate(BaseModel):
    """
    Модель для обновления недавно просмотренных товаров
    """
    product_id: UUID