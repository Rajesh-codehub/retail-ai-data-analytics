import pytest
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from app.models.branch import Branch
from app.models.category import Category
from app.models.product import Product
from app.models.customer import Customer
from app.models.user import User
from app.models.transaction import Transaction
from app.models.sales import Sale
from app.models.inventory_balance import InventoryBalance

def test_create_branch(db):
    """Test creating a branch successfully."""
    branch = Branch(branch_code="HYD-001", branch_name="Hyderabad Central", city="Hyderabad")
    db.add(branch)
    db.commit()
    
    saved_branch = db.query(Branch).filter_by(branch_code="HYD-001").first()
    assert saved_branch is not None
    assert saved_branch.branch_name == "Hyderabad Central"

def test_create_product_with_category(db):
    """Test creating a product linked to a category."""
    category = Category(category_code="GRO", category_name="Grocery")
    db.add(category)
    db.flush()

    product = Product(
        sku="SKU-GRO-001",
        product_name="Rice 5kg",
        category_id=category.id,
        default_price=Decimal("350.00")
    )
    db.add(product)
    db.commit()

    saved_product = db.query(Product).filter_by(sku="SKU-GRO-001").first()
    assert saved_product is not None
    assert saved_product.category.category_name == "Grocery"
    assert saved_product.default_price == Decimal("350.00")

def test_duplicate_sku_rejected(db):
    """Test that inserting a duplicate SKU raises an IntegrityError."""
    category = Category(category_code="GRO", category_name="Grocery")
    db.add(category)
    db.flush()

    p1 = Product(sku="SKU-TEST", product_name="Item 1", category_id=category.id, default_price=Decimal("100.00"))
    db.add(p1)
    db.commit()

    p2 = Product(sku="SKU-TEST", product_name="Item 2", category_id=category.id, default_price=Decimal("150.00"))
    db.add(p2)
    
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_duplicate_user_email_rejected(db):
    """Test that duplicate user emails are rejected."""
    user1 = User(employee_id="EMP-1", name="Alice", email="alice@store.com", password_hash="hash")
    db.add(user1)
    db.commit()

    user2 = User(employee_id="EMP-2", name="Bob", email="alice@store.com", password_hash="hash")
    db.add(user2)

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_duplicate_inventory_branch_product_rejected(db):
    """Test unique constraint on inventory branch_id and product_id combination."""
    branch = Branch(branch_code="B1", branch_name="Branch 1", city="Hyd")
    category = Category(category_code="C1", category_name="Cat 1")
    db.add_all([branch, category])
    db.flush()  # <-- Flush first so category.id is generated

    product = Product(sku="S1", product_name="Prod 1", category_id=category.id, default_price=Decimal("10.00"))
    db.add(product)
    db.flush()

    inv1 = InventoryBalance(branch_id=branch.id, product_id=product.id, quantity_on_hand=Decimal("10"))
    db.add(inv1)
    db.commit()

    inv2 = InventoryBalance(branch_id=branch.id, product_id=product.id, quantity_on_hand=Decimal("5"))
    db.add(inv2)

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_create_transaction_with_sales_lines(db):
    """Test creating a transaction along with associated sales lines."""
    branch = Branch(branch_code="B1", branch_name="Branch 1", city="Hyd")
    customer = Customer(customer_code="C1", customer_name="Customer 1")
    category = Category(category_code="C1", category_name="Cat 1")
    db.add_all([branch, customer, category])
    db.flush()  # <-- Flush first so category.id is generated

    product = Product(sku="S1", product_name="Prod 1", category_id=category.id, default_price=Decimal("50.00"))
    db.add(product)
    db.flush()

    transaction = Transaction(
        branch_id=branch.id,
        customer_id=customer.id,
        total_amount=Decimal("100.00")
    )
    db.add(transaction)
    db.flush()

    sale_line = Sale(
        transaction_id=transaction.id,
        product_id=product.id,
        line_number=1,
        quantity=Decimal("2"),
        unit_price=Decimal("50.00"),
        net_revenue=Decimal("100.00")
    )
    db.add(sale_line)
    db.commit()

    saved_txn = db.query(Transaction).first()
    assert len(saved_txn.sales) == 1
    assert saved_txn.sales[0].net_revenue == Decimal("100.00")

def test_delete_referenced_category_restriction(db):
    """Test that deleting a category cascades or restricts based on model configuration."""
    category = Category(category_code="GRO", category_name="Grocery")
    db.add(category)
    db.flush()

    product = Product(sku="SKU-1", product_name="Item", category_id=category.id, default_price=Decimal("10.00"))
    db.add(product)
    db.commit()

    # Since Category has cascade="all, delete-orphan", deleting category deletes products successfully
    db.delete(category)
    db.commit()

    assert db.query(Product).count() == 0