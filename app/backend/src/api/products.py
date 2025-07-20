from fastapi import APIRouter, Depends, HTTPException, Request
from uuid import UUID
from ..core.models import Product, ProductUpdate
from cassandra.cqlengine.query import DoesNotExist

router = APIRouter(
    prefix="/products",
    tags=["Products"],
)


def get_cassandra_session(request: Request):
    return request.app.state.cassandra_session


@router.get("/", response_model=list[Product])
def list_products(session=Depends(get_cassandra_session)):
    """Получение списка всех товаров."""
    rows = session.execute("SELECT id, name, category, price, quantity FROM products")
    return [Product(id=row.id, name=row.name, category=row.category, price=row.price, quantity=row.quantity) for row in rows]


@router.post("/", response_model=Product, status_code=201)
def create_product(product: Product, session=Depends(get_cassandra_session)):
    """Создание нового товара."""
    session.execute(
        """
        INSERT INTO products (id, name, category, price, quantity)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (product.id, product.name, product.category, product.price, product.quantity)
    )
    return product


@router.get("/{product_id}", response_model=Product)
def get_product(product_id: UUID, session=Depends(get_cassandra_session)):
    """Получение товара по ID."""
    query = "SELECT id, name, category, price, quantity FROM products WHERE id = %s"
    row = session.execute(query, [product_id]).one()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return Product(id=row.id, name=row.name, category=row.category, price=row.price, quantity=row.quantity)


@router.put("/{product_id}", response_model=Product)
def update_product(product_id: UUID, product_update: ProductUpdate, session=Depends(get_cassandra_session)):
    """Обновление товара по ID."""
    # First, get the current product
    get_query = "SELECT id, name, category, price, quantity FROM products WHERE id = %s"
    current_product_row = session.execute(get_query, [product_id]).one()
    if not current_product_row:
        raise HTTPException(status_code=404, detail="Product not found")

    current_product = Product(
        id=current_product_row.id,
        name=current_product_row.name,
        category=current_product_row.category,
        price=current_product_row.price,
        quantity=current_product_row.quantity
    )
    updated_product_data = product_update.model_dump(exclude_unset=True)
    updated_product = current_product.model_copy(update=updated_product_data)

    update_query = """
        UPDATE products
        SET name = %s, category = %s, price = %s, quantity = %s
        WHERE id = %s
    """
    session.execute(
        update_query,
        (
            updated_product.name,
            updated_product.category,
            updated_product.price,
            updated_product.quantity,
            product_id,
        ),
    )
    return updated_product


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: UUID, session=Depends(get_cassandra_session)):
    """Удаление товара по ID."""
    query = "DELETE FROM products WHERE id = %s"
    session.execute(query, [product_id])
    return
