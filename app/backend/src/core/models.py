# Файл: app/backend/src/core/models.py
import uuid
from decimal import Decimal
from pydantic import BaseModel, Field
from uuid import UUID, uuid4

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


class Product(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    category: str
    price: Decimal
    quantity: int

class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    price: Decimal | None = None
    quantity: int | None = None