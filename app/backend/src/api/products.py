from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from uuid import UUID
from ..core.models import ProductCreate, ProductOut, ProductDetailsOut, ProductUpdate, CategoryOut, PaginatedProductsResponse
from ..auth import get_user_info, get_admin_user
from ..tracing import get_tracer
# Импортируем модуль профилирования
from ..profiling import profile_endpoint, profile_context, get_profile_stats, list_available_profiles
from cassandra.cqlengine.query import DoesNotExist
import uuid
import time
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


def get_metrics_collector():
    """Получить сборщик метрик"""
    try:
        from ..services.metrics import metrics_collector
        return metrics_collector
    except ImportError:
        return None


@router.get(
    "/", 
    response_model=PaginatedProductsResponse,
    summary="📋 Получение каталога товаров",
    description="""
    ## Описание
    Возвращает список товаров с поддержкой пагинации, сортировки и фильтрации.
    
    **Ограничения доступа:**
    - 👤 **Обычные пользователи**: могут получать товары только конкретной категории (параметр `category` обязателен)
    - 👑 **Администраторы**: могут получать все товары без ограничений
    
    ## Параметры фильтрации
    - � **category** - категория товаров (обязательна для обычных пользователей)
    - �💰 **min_price** - минимальная цена (включительно)
    - 💰 **max_price** - максимальная цена (включительно)
    
    ## Сортировка
    - 📝 **sort_by**: `name` (по названию) или `price` (по цене)
    - 🔄 **sort_order**: `asc` (по возрастанию) или `desc` (по убыванию)
    
    ## Пагинация
    - 📄 **skip** - количество товаров для пропуска (offset)
    - 📊 **limit** - максимальное количество товаров на странице (1-100)
    """,
    responses={
        200: {
            "description": "✅ Список товаров успешно получен"
        },
        400: {
            "description": "❌ Неверные параметры запроса",
            "model": ValidationError
        },
        401: {
            "description": "🔐 Требуется аутентификация"
        },
        403: {
            "description": "🚫 Обычные пользователи должны указать категорию"
        }
    }
)
@profile_endpoint("list_products")
def list_products(
    session=Depends(get_cassandra_session),
    user_info=Depends(get_user_info),
    category: Optional[str] = Query(None, description="📁 Категория товаров (обязательна для обычных пользователей)"),
    skip: int = Query(0, ge=0, description="📄 Количество товаров для пропуска"),
    limit: int = Query(100, ge=1, le=100, description="📊 Максимальное количество товаров на странице"),
    sort_by: Optional[str] = Query(None, regex="^(name|price)$", description="🔤 Поле для сортировки: name или price"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="🔄 Порядок сортировки: asc (по возрастанию) или desc (по убыванию)"),
    min_price: Optional[float] = Query(None, ge=0, description="💰 Минимальная цена фильтра (включительно)"),
    max_price: Optional[float] = Query(None, ge=0, description="💰 Максимальная цена фильтра (включительно)")
):
    """
    ## Получение каталога товаров с контролем доступа
    
    ### Логика контроля доступа:
    - 👤 **Обычные пользователи**: должны указать параметр `category`
    - 👑 **Администраторы**: могут получать все товары или фильтровать по категории
    
    ### Логика работы:
    1. � Проверка прав доступа и обязательности категории
    2. �🔍 Применение фильтров по категории и цене
    3. 🔤 Выполнение сортировки  
    4. 📄 Применение пагинации
    5. 📊 Расчет метаданных для навигации
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span("list_products") as span:
        metrics_collector = get_metrics_collector()
        start_time = time.time()
        
        # Добавляем атрибуты запроса в span
        span.set_attribute("query.category", category or "all")
        span.set_attribute("query.skip", skip)
        span.set_attribute("query.limit", limit)
        span.set_attribute("query.sort_by", sort_by or "none")
        span.set_attribute("query.sort_order", sort_order)
        if min_price is not None:
            span.set_attribute("query.min_price", min_price)
        if max_price is not None:
            span.set_attribute("query.max_price", max_price)
        
        try:
            # Проверка контроля доступа
            is_admin = user_info and user_info.get("is_admin", False)
            span.set_attribute("user.is_admin", is_admin)
            
            # Если пользователь не администратор, категория обязательна
            if not is_admin and not category:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Обычные пользователи должны указать категорию товаров. Используйте параметр 'category'."
                )
            
            # Валидация параметров цены
            if min_price is not None and max_price is not None and min_price > max_price:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="min_price не может быть больше max_price"
                )
            
            # Построение запроса
            if category:
                # Фильтрация по категории
                query = "SELECT id, name, category, price FROM products WHERE category = %s"
                params = [category]
            else:
                # Только для администраторов - все товары
                query = "SELECT id, name, category, price FROM products"
                params = []
            
            # Добавление фильтров по цене
            price_filters = []
            if min_price is not None:
                price_filters.append("price >= %s")
                params.append(str(min_price))
            if max_price is not None:
                price_filters.append("price <= %s")
                params.append(str(max_price))
            
            if price_filters:
                if category:
                    query += " AND " + " AND ".join(price_filters)
                else:
                    query += " WHERE " + " AND ".join(price_filters)
            
            # Добавляем ALLOW FILTERING для запросов с фильтрацией
            if category or price_filters:
                query += " ALLOW FILTERING"
            
            # Выполнение запроса
            with tracer.start_as_current_span("database_query") as db_span:
                db_span.set_attribute("db.operation", "select")
                db_span.set_attribute("db.table", "products")
                db_span.set_attribute("db.query_type", "select_products")
                db_span.set_attribute("db.has_price_filter", len(price_filters) > 0)
                db_span.set_attribute("db.has_category_filter", category is not None)
                
                query_start_time = time.time()
                rows = session.execute(query, params)
                
                if metrics_collector:
                    query_duration = time.time() - query_start_time
                    metrics_collector.record_db_query('select_products', query_duration)
                    db_span.set_attribute("db.duration_seconds", query_duration)
            
            # Преобразование в список для сортировки и пагинации
            with tracer.start_as_current_span("process_results") as process_span:
                products = [ProductOut(product_id=row.id, name=row.name, category=row.category, price=row.price) for row in rows]
                process_span.set_attribute("products.raw_count", len(products))
            
            # Получение общего количества для метаданных пагинации
            total_count = len(products)
            span.set_attribute("results.total_count", total_count)
            
            # Применение сортировки
            if sort_by:
                with tracer.start_as_current_span("sort_products") as sort_span:
                    sort_span.set_attribute("sort.field", sort_by)
                    sort_span.set_attribute("sort.order", sort_order)
                    
                    reverse = sort_order == "desc"
                    if sort_by == "name":
                        products.sort(key=lambda x: x.name, reverse=reverse)
                    elif sort_by == "price":
                        products.sort(key=lambda x: float(x.price), reverse=reverse)
            
            # Применение пагинации
            with tracer.start_as_current_span("paginate_products") as page_span:
                page_span.set_attribute("pagination.skip", skip)
                page_span.set_attribute("pagination.limit", limit)
                
                paginated_products = products[skip:skip+limit]
                page_span.set_attribute("pagination.returned_count", len(paginated_products))
                
                # Расчет метаданных пагинации
                total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
                
                span.set_attribute("results.pages_total", total_pages)
                span.set_attribute("results.current_page", (skip // limit) + 1)
            
            return {
                "items": paginated_products,
                "total": total_count,
                "page": (skip // limit) + 1,
                "pages": total_pages,
                "has_next": skip + limit < total_count,
                "has_prev": skip > 0
            }
                
        except HTTPException:
            span.set_attribute("error", "http_exception")
            raise
        except Exception as e:
            span.set_attribute("error", "unknown_exception")
            span.set_attribute("error.message", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при получении списка товаров: {str(e)}"
            )


@router.post(
    "/", 
    response_model=ProductDetailsOut, 
    status_code=201,
    summary="➕ Создание нового товара (только для администраторов)",
    description="""
    ## Описание
    Добавляет новый товар в каталог магазина.
    
    **⚠️ Требуется:**
    - 🔐 Аутентификация
    - 👑 Права администратора
    
    ## Требования к данным
    - 🏷️ **name** - уникальное название товара (1-200 символов)
    - 📁 **category** - категория товара (1-50 символов)  
    - 💰 **price** - цена товара (больше 0, до 99,999,999.99)
    - 📦 **stock_count** - количество на складе (не отрицательное число)
    - 📝 **description** - описание товара (опционально, до 1000 символов)
    - 🏭 **manufacturer** - производитель (опционально, до 100 символов)
    """,
    responses={
        201: {
            "description": "✅ Товар успешно создан"
        },
        401: {
            "description": "🔐 Требуется аутентификация"
        },
        403: {
            "description": "👑 Требуются права администратора"
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
@profile_endpoint("create_product")
def create_product(
    product: ProductCreate, 
    session=Depends(get_cassandra_session),
    admin_user=Depends(get_admin_user)
):
    """Создание нового товара."""
    tracer = get_tracer()
    
    with tracer.start_as_current_span("create_product") as span:
        span.set_attribute("product.name", product.name)
        span.set_attribute("product.category", product.category)
        span.set_attribute("product.price", float(product.price))
        span.set_attribute("product.stock_count", product.stock_count)
        span.set_attribute("admin.username", admin_user["username"])
        
        metrics_collector = get_metrics_collector()
        
        with tracer.start_as_current_span("generate_product_id"):
            product_id = uuid.uuid4()
            span.set_attribute("product.id", str(product_id))
        
        with tracer.start_as_current_span("database_insert") as db_span:
            db_span.set_attribute("db.operation", "insert")
            db_span.set_attribute("db.table", "products")
            db_span.set_attribute("db.query_type", "insert_product")
            
            query_start_time = time.time()
            session.execute(
                """
                INSERT INTO products (id, name, category, price, quantity, description, manufacturer)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (product_id, product.name, product.category, product.price, product.stock_count, product.description, product.manufacturer)
            )
            
            if metrics_collector:
                query_duration = time.time() - query_start_time
                metrics_collector.record_db_query('insert_product', query_duration)
                db_span.set_attribute("db.duration_seconds", query_duration)
        
        span.set_attribute("product.created", True)
        return ProductDetailsOut(product_id=product_id, **product.model_dump())


@router.get("/{product_id}", response_model=ProductDetailsOut)
@profile_endpoint("get_product")
def get_product(product_id: UUID, session=Depends(get_cassandra_session)):
    """Получение товара по ID."""
    tracer = get_tracer()
    
    with tracer.start_as_current_span("get_product") as span:
        span.set_attribute("product.id", str(product_id))
        
        metrics_collector = get_metrics_collector()
        
        query = "SELECT id, name, category, price, quantity, description, manufacturer FROM products WHERE id = %s"
        
        with tracer.start_as_current_span("database_query") as db_span:
            db_span.set_attribute("db.operation", "select")
            db_span.set_attribute("db.table", "products")
            db_span.set_attribute("db.query_type", "select_product_by_id")
            
            query_start_time = time.time()
            row = session.execute(query, [product_id]).one()
            
            if metrics_collector:
                query_duration = time.time() - query_start_time
                metrics_collector.record_db_query('select_product_by_id', query_duration)
                db_span.set_attribute("db.duration_seconds", query_duration)
        
        if not row:
            span.set_attribute("product.found", False)
            raise HTTPException(status_code=404, detail="Product not found")
            
        span.set_attribute("product.found", True)
        span.set_attribute("product.name", row.name)
        span.set_attribute("product.category", row.category)
        span.set_attribute("product.price", float(row.price))
        span.set_attribute("product.stock_count", row.quantity)
        
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
@profile_endpoint("update_product")
def update_product(product_id: UUID, product_update: ProductUpdate, session=Depends(get_cassandra_session)):
    """Обновление товара по ID."""
    metrics_collector = get_metrics_collector()
    
    # First, get the current product
    get_query = "SELECT id, name, category, price, quantity, description, manufacturer FROM products WHERE id = %s"
    
    query_start_time = time.time()
    current_product_row = session.execute(get_query, [product_id]).one()
    
    if metrics_collector:
        query_duration = time.time() - query_start_time
        metrics_collector.record_db_query('select_product_for_update', query_duration)
    
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
    
    query_start_time = time.time()
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
    
    if metrics_collector:
        query_duration = time.time() - query_start_time
        metrics_collector.record_db_query('update_product', query_duration)
    
    return current_product

@router.delete("/{product_id}", status_code=204)
@profile_endpoint("delete_product")
def delete_product(product_id: UUID, session=Depends(get_cassandra_session)):
    """Удаление товара по ID."""
    metrics_collector = get_metrics_collector()
    
    query = "DELETE FROM products WHERE id = %s"
    
    query_start_time = time.time()
    session.execute(query, [product_id])
    
    if metrics_collector:
        query_duration = time.time() - query_start_time
        metrics_collector.record_db_query('delete_product', query_duration)
    
    return

# New endpoints

@router.get("/categories/list", response_model=List[CategoryOut])
def list_categories(session=Depends(get_cassandra_session)):
    """Получение списка доступных категорий и количества товаров в каждой."""
    metrics_collector = get_metrics_collector()
    
    # Get all products' categories
    categories_query = "SELECT category FROM products ALLOW FILTERING"
    
    query_start_time = time.time()
    categories_rows = session.execute(categories_query)
    
    if metrics_collector:
        query_duration = time.time() - query_start_time
        metrics_collector.record_db_query('select_categories', query_duration)
    
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
@profile_endpoint("get_products_by_category")
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
