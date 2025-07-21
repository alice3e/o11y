from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from uuid import UUID
from ..core.models import ProductCreate, ProductOut, ProductDetailsOut, ProductUpdate, CategoryOut, PaginatedProductsResponse
from cassandra.cqlengine.query import DoesNotExist
import uuid
from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel

router = APIRouter(
    prefix="/products",
    tags=["🛍️ Products & Catalog"],
    responses={
        500: {"description": "❌ Внутренняя ошибка сервера"},
        503: {"description": "⚠️ База данных недоступна"}
    }
)

# Модели для документации
class ProductNotFoundError(BaseModel):
    """Модель ошибки 'Товар не найден'"""
    detail: str = "Product not found"

class ValidationError(BaseModel):
    """Модель ошибки валидации"""
    detail: str = "Validation error"
    
class DatabaseError(BaseModel):
    """Модель ошибки базы данных"""
    detail: str = "Database connection error"


def get_cassandra_session(request: Request):
    return request.app.state.cassandra_session


@router.get(
    "/", 
    response_model=PaginatedProductsResponse,
    summary="📋 Получение каталога товаров",
    description="""
    ## Описание
    Возвращает список товаров с поддержкой пагинации, сортировки и фильтрации по цене.
    
    ## Параметры фильтрации
    - 💰 **min_price** - минимальная цена (включительно)
    - 💰 **max_price** - максимальная цена (включительно)
    
    ## Сортировка
    - 📝 **sort_by**: `name` (по названию) или `price` (по цене)
    - 🔄 **sort_order**: `asc` (по возрастанию) или `desc` (по убыванию)
    
    ## Пагинация
    - 📄 **skip** - количество товаров для пропуска (offset)
    - 📊 **limit** - максимальное количество товаров на странице (1-100)
    
    ## Возвращаемые данные
    ```json
    {
        "items": [...],      // Список товаров
        "total": 150,        // Общее количество товаров
        "page": 1,           // Текущая страница
        "pages": 2,          // Общее количество страниц
        "has_next": true,    // Есть ли следующая страница
        "has_prev": false    // Есть ли предыдущая страница
    }
    ```
    """,
    responses={
        200: {
            "description": "✅ Список товаров успешно получен",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "product_id": "550e8400-e29b-41d4-a716-446655440000",
                                "name": "Молоко 'Простоквашино' 3.2%",
                                "category": "Молочные продукты",
                                "price": 99.90
                            }
                        ],
                        "total": 1,
                        "page": 1,
                        "pages": 1,
                        "has_next": False,
                        "has_prev": False
                    }
                }
            }
        },
        400: {
            "description": "❌ Неверные параметры запроса",
            "model": ValidationError
        }
    }
)
def list_products(
    session=Depends(get_cassandra_session),
    skip: int = Query(0, ge=0, description="📄 Количество товаров для пропуска"),
    limit: int = Query(100, ge=1, le=100, description="📊 Максимальное количество товаров на странице"),
    sort_by: Optional[str] = Query(None, regex="^(name|price)$", description="🔤 Поле для сортировки: name или price"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="🔄 Порядок сортировки: asc (по возрастанию) или desc (по убыванию)"),
    min_price: Optional[float] = Query(None, ge=0, description="💰 Минимальная цена фильтра (включительно)"),
    max_price: Optional[float] = Query(None, ge=0, description="💰 Максимальная цена фильтра (включительно)")
):
    """
    ## Получение каталога товаров
    
    Возвращает пагинированный список товаров из базы данных с возможностью фильтрации и сортировки.
    
    ### Логика работы:
    1. 🔍 Применяются фильтры по цене (если указаны)
    2. 🔤 Выполняется сортировка (если указана)  
    3. 📄 Применяется пагинация
    4. 📊 Рассчитываются метаданные для навигации
    
    ### Примечание по производительности:
    ⚠️ Фильтрация по цене использует `ALLOW FILTERING` в Cassandra, что не рекомендуется в продакшене.
    В реальном приложении следует использовать вторичные индексы или материализованные представления.
    """
    try:
        # Валидация параметров
        if min_price is not None and max_price is not None and min_price > max_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="min_price не может быть больше max_price"
            )
        
        # Start with basic query
        query = "SELECT id, name, category, price FROM products"
        params = []
        
        # Apply price filtering if provided
        filters = []
        if min_price is not None:
            filters.append("price >= %s")
            params.append(str(min_price))  # Передаём как строку для Cassandra
        if max_price is not None:
            filters.append("price <= %s")
            params.append(str(max_price))  # Передаём как строку для Cassandra
        
        if filters:
            query += " WHERE " + " AND ".join(filters) + " ALLOW FILTERING"
        
        # Execute the query
        rows = session.execute(query, params)
        
        # Convert to list for sorting and pagination
        products = [ProductOut(product_id=row.id, name=row.name, category=row.category, price=row.price) for row in rows]
        
        # Get total count for pagination metadata
        total_count = len(products)
        
        # Apply sorting
        if sort_by:
            reverse = sort_order == "desc"
            if sort_by == "name":
                products.sort(key=lambda x: x.name, reverse=reverse)
            elif sort_by == "price":
                products.sort(key=lambda x: float(x.price), reverse=reverse)
        
        # Apply pagination
        paginated_products = products[skip:skip+limit]
        
        # Calculate pagination metadata
        total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
        
        return {
            "items": paginated_products,
            "total": total_count,
            "page": (skip // limit) + 1,
            "pages": total_pages,
            "has_next": skip + limit < total_count,
            "has_prev": skip > 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении списка товаров: {str(e)}"
        )


@router.post(
    "/", 
    response_model=ProductDetailsOut, 
    status_code=201,
    summary="➕ Создание нового товара",
    description="""
    ## Описание
    Добавляет новый товар в каталог магазина.
    
    ## Требования к данным
    - 🏷️ **name** - уникальное название товара (1-200 символов)
    - 📁 **category** - категория товара (1-50 символов)  
    - 💰 **price** - цена товара (больше 0, до 99,999,999.99)
    - 📦 **stock_count** - количество на складе (не отрицательное число)
    - 📝 **description** - описание товара (опционально, до 1000 символов)
    - 🏭 **manufacturer** - производитель (опционально, до 100 символов)
    
    ## Возвращаемые данные
    Полная информация о созданном товаре включая присвоенный UUID.
    """,
    responses={
        201: {
            "description": "✅ Товар успешно создан",
            "content": {
                "application/json": {
                    "example": {
                        "product_id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Молоко 'Простоквашино' 3.2%",
                        "category": "Молочные продукты",
                        "price": 99.90,
                        "stock_count": 150,
                        "description": "Отборное пастеризованное молоко",
                        "manufacturer": "ООО 'Данон Россия'"
                    }
                }
            }
        },
        400: {
            "description": "❌ Неверные данные товара",
            "model": ValidationError
        },
        500: {
            "description": "❌ Ошибка при создании товара",
            "model": DatabaseError
        }
    }
)
def create_product(product: ProductCreate, session=Depends(get_cassandra_session)):
    """Создание нового товара."""
    product_id = uuid.uuid4()
    session.execute(
        """
        INSERT INTO products (id, name, category, price, quantity, description, manufacturer)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (product_id, product.name, product.category, product.price, product.stock_count, product.description, product.manufacturer)
    )
    return ProductDetailsOut(product_id=product_id, **product.model_dump())


@router.get("/{product_id}", response_model=ProductDetailsOut)
def get_product(product_id: UUID, session=Depends(get_cassandra_session)):
    """Получение товара по ID."""
    query = "SELECT id, name, category, price, quantity, description, manufacturer FROM products WHERE id = %s"
    row = session.execute(query, [product_id]).one()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductDetailsOut(
        product_id=row.id,
        name=row.name,
        category=row.category,
        price=row.price,
        stock_count=row.quantity,
        description=row.description,
        manufacturer=row.manufacturer
    )


@router.put("/{product_id}", response_model=ProductDetailsOut)
def update_product(product_id: UUID, product_update: ProductUpdate, session=Depends(get_cassandra_session)):
    """Обновление товара по ID."""
    # First, get the current product
    get_query = "SELECT id, name, category, price, quantity, description, manufacturer FROM products WHERE id = %s"
    current_product_row = session.execute(get_query, [product_id]).one()
    if not current_product_row:
        raise HTTPException(status_code=404, detail="Product not found")

    current_product = ProductDetailsOut(
        product_id=current_product_row.id,
        name=current_product_row.name,
        category=current_product_row.category,
        price=current_product_row.price,
        stock_count=current_product_row.quantity,
        description=current_product_row.description,
        manufacturer=current_product_row.manufacturer,
    )
    
    update_data = product_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_product, key, value)

    update_query = """
        UPDATE products
        SET name = %s, category = %s, price = %s, quantity = %s, description = %s, manufacturer = %s
        WHERE id = %s
    """
    session.execute(
        update_query,
        (
            current_product.name,
            current_product.category,
            current_product.price,
            current_product.stock_count,
            current_product.description,
            current_product.manufacturer,
            product_id,
        ),
    )
    return current_product

@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: UUID, session=Depends(get_cassandra_session)):
    """Удаление товара по ID."""
    query = "DELETE FROM products WHERE id = %s"
    session.execute(query, [product_id])
    return

# New endpoints

@router.get("/categories/list", response_model=List[CategoryOut])
def list_categories(session=Depends(get_cassandra_session)):
    """Получение списка доступных категорий и количества товаров в каждой."""
    # Get all products' categories
    categories_query = "SELECT category FROM products ALLOW FILTERING"
    categories_rows = session.execute(categories_query)
    
    # Use a dictionary to track unique categories and counts
    category_counts = {}
    for row in categories_rows:
        category = row.category
        if category in category_counts:
            category_counts[category] += 1
        else:
            category_counts[category] = 1
    
    # Convert to result format
    result = []
    for category, count in category_counts.items():
        result.append(CategoryOut(
            name=category,
            product_count=count
        ))
    
    return result

@router.get("/by-category/{category}", response_model=PaginatedProductsResponse)
def get_products_by_category(
    category: str,
    session=Depends(get_cassandra_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    sort_by: Optional[str] = Query(None, description="Field to sort by: name, price"),
    sort_order: Optional[str] = Query("asc", description="Sort order: asc or desc"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter")
):
    """Получение списка товаров определенной категории с пагинацией, сортировкой и фильтрацией."""
    # Start with base query
    query = "SELECT id, name, category, price FROM products WHERE category = %s"
    params = [category]
    
    # Apply price filtering if provided
    filters = []
    if min_price is not None:
        filters.append("price >= %s")
        params.append(Decimal(str(min_price)))
    if max_price is not None:
        filters.append("price <= %s")
        params.append(Decimal(str(max_price)))
    
    if filters:
        query += " AND " + " AND ".join(filters)
    
    # Add ALLOW FILTERING since we're filtering on non-primary key
    query += " ALLOW FILTERING"
    
    # Execute the query
    rows = session.execute(query, params)
    
    # Convert to list for sorting and pagination
    products = [ProductOut(product_id=row.id, name=row.name, category=row.category, price=row.price) for row in rows]
    
    # Get total count for pagination metadata
    total_count = len(products)
    
    # Apply sorting
    if sort_by:
        reverse = sort_order.lower() == "desc"
        if sort_by == "name":
            products.sort(key=lambda x: x.name, reverse=reverse)
        elif sort_by == "price":
            products.sort(key=lambda x: float(x.price), reverse=reverse)
    
    # Apply pagination
    paginated_products = products[skip:skip+limit]
    
    # Calculate pagination metadata
    total_pages = (total_count + limit - 1) // limit if limit > 0 else 0
    
    return {
        "items": paginated_products,
        "total": total_count,
        "page": (skip // limit) + 1 if limit > 0 else 1,
        "pages": total_pages,
        "has_next": skip + limit < total_count,
        "has_prev": skip > 0
    }
