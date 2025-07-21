from fastapi import APIRouter, Depends, HTTPException, Request, Query
from uuid import UUID
from ..core.models import ProductCreate, ProductOut, ProductDetailsOut, ProductUpdate, CategoryOut, PaginatedProductsResponse
from cassandra.cqlengine.query import DoesNotExist
import uuid
from typing import List, Optional
from decimal import Decimal

router = APIRouter(
    prefix="/products",
    tags=["Products"],
)


def get_cassandra_session(request: Request):
    return request.app.state.cassandra_session


@router.get("/", response_model=PaginatedProductsResponse)
def list_products(
    session=Depends(get_cassandra_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    sort_by: Optional[str] = Query(None, description="Field to sort by: name, price"),
    sort_order: Optional[str] = Query("asc", description="Sort order: asc or desc"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter")
):
    """Получение списка всех товаров с пагинацией, сортировкой и фильтрацией."""
    # Start with basic query
    query = "SELECT id, name, category, price FROM products"
    params = []
    
    # Apply price filtering if provided (would need secondary indexes in production)
    # Note: This approach requires ALLOW FILTERING which is not recommended for production
    filters = []
    if min_price is not None:
        filters.append("price >= %s")
        params.append(Decimal(str(min_price)))
    if max_price is not None:
        filters.append("price <= %s")
        params.append(Decimal(str(max_price)))
    
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
        reverse = sort_order.lower() == "desc"
        if sort_by == "name":
            products.sort(key=lambda x: x.name, reverse=reverse)
        elif sort_by == "price":
            products.sort(key=lambda x: float(x.price), reverse=reverse)
    
    # Apply pagination
    paginated_products = products[skip:skip+limit]
    
    # Calculate pagination metadata
    total_pages = (total_count + limit - 1) // limit
    
    return {
        "items": paginated_products,
        "total": total_count,
        "page": (skip // limit) + 1,
        "pages": total_pages,
        "has_next": skip + limit < total_count,
        "has_prev": skip > 0
    }


@router.post("/", response_model=ProductDetailsOut, status_code=201)
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
    # This query will get all unique categories
    categories_query = "SELECT DISTINCT category FROM products"
    categories_rows = session.execute(categories_query)
    
    result = []
    for category_row in categories_rows:
        category = category_row.category
        # Count products in this category
        count_query = "SELECT COUNT(*) as count FROM products WHERE category = %s ALLOW FILTERING"
        count_row = session.execute(count_query, [category]).one()
        
        result.append(CategoryOut(
            name=category,
            product_count=count_row.count
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
