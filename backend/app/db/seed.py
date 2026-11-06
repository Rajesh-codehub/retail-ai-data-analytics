from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from app.db.database import SessionLocal  # Adjust import based on your database.py setup
from app.models.branch import Branch
from app.models.category import Category
from app.models.product import Product
from app.models.customer import Customer
from app.models.user import User
from app.models.transaction import Transaction
from app.models.sales import Sale

def seed_database(db: Session) -> None:
    print("🌱 Starting database seeding...")

    try:
        # ==========================================
        # 1. Seed Branches (3 records)
        # ==========================================
        branch_data = [
            {"branch_code": "HYD-001", "branch_name": "Hyderabad Central", "city": "Hyderabad", "timezone": "Asia/Kolkata"},
            {"branch_code": "SEC-002", "branch_name": "Secunderabad", "city": "Secunderabad", "timezone": "Asia/Kolkata"},
            {"branch_code": "KUK-003", "branch_name": "Kukatpally", "city": "Hyderabad", "timezone": "Asia/Kolkata"},
        ]
        
        branches = {}
        for b_info in branch_data:
            branch = db.query(Branch).filter_by(branch_code=b_info["branch_code"]).first()
            if not branch:
                branch = Branch(**b_info)
                db.add(branch)
                db.flush()  # Flush to generate IDs
                print(f"  + Created Branch: {branch.branch_name}")
            branches[b_info["branch_code"]] = branch

        # ==========================================
        # 2. Seed Categories (5 records)
        # ==========================================
        category_data = [
            {"category_code": "GRO", "category_name": "Grocery"},
            {"category_code": "DAI", "category_name": "Dairy"},
            {"category_code": "PER", "category_name": "Personal Care"},
            {"category_code": "BEV", "category_name": "Beverages"},
            {"category_code": "SNA", "category_name": "Snacks"},
        ]

        categories = {}
        for c_info in category_data:
            category = db.query(Category).filter_by(category_code=c_info["category_code"]).first()
            if not category:
                category = Category(**c_info)
                db.add(category)
                db.flush()
                print(f"  + Created Category: {category.category_name}")
            categories[c_info["category_code"]] = category

        # ==========================================
        # 3. Seed Products (10 records referencing categories)
        # ==========================================
        product_data = [
            {"sku": "SKU-GRO-001", "product_name": "Rice 5kg", "category_code": "GRO", "unit_of_measure": "bag", "default_price": Decimal("350.00")},
            {"sku": "SKU-GRO-002", "product_name": "Cooking Oil 1L", "category_code": "GRO", "unit_of_measure": "bottle", "default_price": Decimal("150.00")},
            {"sku": "SKU-GRO-003", "product_name": "Toor Dal 1kg", "category_code": "GRO", "unit_of_measure": "kg", "default_price": Decimal("120.00")},
            {"sku": "SKU-DAI-001", "product_name": "Milk 1L", "category_code": "DAI", "unit_of_measure": "packet", "default_price": Decimal("60.00")},
            {"sku": "SKU-DAI-002", "product_name": "Curd 500g", "category_code": "DAI", "unit_of_measure": "cup", "default_price": Decimal("35.00")},
            {"sku": "SKU-PER-001", "product_name": "Shampoo", "category_code": "PER", "unit_of_measure": "bottle", "default_price": Decimal("180.00")},
            {"sku": "SKU-PER-002", "product_name": "Soap Bar", "category_code": "PER", "unit_of_measure": "pcs", "default_price": Decimal("40.00")},
            {"sku": "SKU-BEV-001", "product_name": "Green Tea 25bags", "category_code": "BEV", "unit_of_measure": "box", "default_price": Decimal("250.00")},
            {"sku": "SKU-BEV-002", "product_name": "Fruit Juice 1L", "category_code": "BEV", "unit_of_measure": "bottle", "default_price": Decimal("110.00")},
            {"sku": "SKU-SNA-001", "product_name": "Mixed Namkeen 400g", "category_code": "SNA", "unit_of_measure": "pack", "default_price": Decimal("90.00")},
        ]

        products = {}
        for p_info in product_data:
            product = db.query(Product).filter_by(sku=p_info["sku"]).first()
            if not product:
                cat = categories[p_info["category_code"]]
                product = Product(
                    sku=p_info["sku"],
                    product_name=p_info["product_name"],
                    category_id=cat.id,
                    unit_of_measure=p_info["unit_of_measure"],
                    default_price=p_info["default_price"]
                )
                db.add(product)
                db.flush()
                print(f"  + Created Product: {product.product_name}")
            products[p_info["sku"]] = product

        # ==========================================
        # 4. Seed Customers (5 records)
        # ==========================================
        customer_data = [
            {"customer_code": "CUST-001", "customer_name": "Rahul Verma"},
            {"customer_code": "CUST-002", "customer_name": "Priya Reddy"},
            {"customer_code": "CUST-003", "customer_name": "Amit Kumar"},
            {"customer_code": "CUST-004", "customer_name": "Sneha Gupta"},
            {"customer_code": "CUST-005", "customer_name": "Kiran Rao"},
        ]

        customers = {}
        for cust_info in customer_data:
            customer = db.query(Customer).filter_by(customer_code=cust_info["customer_code"]).first()
            if not customer:
                customer = Customer(**cust_info)
                db.add(customer)
                db.flush()
                print(f"  + Created Customer: {customer.customer_name}")
            customers[cust_info["customer_code"]] = customer

        # ==========================================
        # 5. Seed Users (3 records referencing branches)
        # ==========================================
        user_data = [
            {"employee_id": "EMP-101", "name": "Manager Hyderabad", "email": "hyd.mgr@store.com", "password_hash": "hashed_pw_1", "role": "manager", "branch_code": "HYD-001"},
            {"employee_id": "EMP-102", "name": "Cashier Secunderabad", "email": "sec.cashier@store.com", "password_hash": "hashed_pw_2", "role": "employee", "branch_code": "SEC-002"},
            {"employee_id": "EMP-103", "name": "Staff Kukatpally", "email": "kuk.staff@store.com", "password_hash": "hashed_pw_3", "role": "employee", "branch_code": "KUK-003"},
        ]

        for u_info in user_data:
            user = db.query(User).filter_by(employee_id=u_info["employee_id"]).first()
            if not user:
                branch = branches[u_info["branch_code"]]
                user = User(
                    employee_id=u_info["employee_id"],
                    name=u_info["name"],
                    email=u_info["email"],
                    password_hash=u_info["password_hash"],
                    role=u_info["role"],
                    branch_id=branch.id
                )
                db.add(user)
                print(f"  + Created User: {user.name}")

        db.flush()

        # ==========================================
        # 6 & 7. Seed Transactions (10) and Sales Lines (20)
        # ==========================================
        # Predefined mapping to fulfill sample requirements
        tx_specs = [
            {"source_id": "TXN-2026-001", "branch_code": "HYD-001", "cust_code": "CUST-001", "lines": [
                {"sku": "SKU-GRO-001", "qty": Decimal("2"), "price": Decimal("350.00")},
                {"sku": "SKU-GRO-002", "qty": Decimal("3"), "price": Decimal("150.00")}
            ]},
            {"source_id": "TXN-2026-002", "branch_code": "SEC-002", "cust_code": "CUST-002", "lines": [
                {"sku": "SKU-DAI-001", "qty": Decimal("5"), "price": Decimal("60.00")}
            ]},
            {"source_id": "TXN-2026-003", "branch_code": "KUK-003", "cust_code": "CUST-003", "lines": [
                {"sku": "SKU-PER-001", "qty": Decimal("2"), "price": Decimal("180.00")},
                {"sku": "SKU-PER-002", "qty": Decimal("4"), "price": Decimal("40.00")}
            ]},
            {"source_id": "TXN-2026-004", "branch_code": "HYD-001", "cust_code": "CUST-004", "lines": [
                {"sku": "SKU-BEV-001", "qty": Decimal("1"), "price": Decimal("250.00")},
                {"sku": "SKU-SNA-001", "qty": Decimal("2"), "price": Decimal("90.00")}
            ]},
            {"source_id": "TXN-2026-005", "branch_code": "SEC-002", "cust_code": "CUST-005", "lines": [
                {"sku": "SKU-GRO-003", "qty": Decimal("2"), "price": Decimal("120.00")},
                {"sku": "SKU-DAI-002", "qty": Decimal("3"), "price": Decimal("35.00")}
            ]},
            {"source_id": "TXN-2026-006", "branch_code": "KUK-003", "cust_code": "CUST-001", "lines": [
                {"sku": "SKU-BEV-002", "qty": Decimal("2"), "price": Decimal("110.00")},
                {"sku": "SKU-GRO-002", "qty": Decimal("1"), "price": Decimal("150.00")}
            ]},
            {"source_id": "TXN-2026-007", "branch_code": "HYD-001", "cust_code": "CUST-002", "lines": [
                {"sku": "SKU-PER-001", "qty": Decimal("1"), "price": Decimal("180.00")},
                {"sku": "SKU-DAI-001", "qty": Decimal("2"), "price": Decimal("60.00")}
            ]},
            {"source_id": "TXN-2026-008", "branch_code": "SEC-002", "cust_code": "CUST-003", "lines": [
                {"sku": "SKU-SNA-001", "qty": Decimal("3"), "price": Decimal("90.00")},
                {"sku": "SKU-GRO-001", "qty": Decimal("1"), "price": Decimal("350.00")}
            ]},
            {"source_id": "TXN-2026-009", "branch_code": "KUK-003", "cust_code": "CUST-004", "lines": [
                {"sku": "SKU-BEV-001", "qty": Decimal("2"), "price": Decimal("250.00")},
                {"sku": "SKU-DAI-002", "qty": Decimal("4"), "price": Decimal("35.00")}
            ]},
            {"source_id": "TXN-2026-010", "branch_code": "HYD-001", "cust_code": "CUST-005", "lines": [
                {"sku": "SKU-GRO-003", "qty": Decimal("5"), "price": Decimal("120.00")},
                {"sku": "SKU-PER-002", "qty": Decimal("2"), "price": Decimal("40.00")}
            ]},
        ]

        for tx_info in tx_specs:
            existing_tx = db.query(Transaction).filter_by(source_transaction_id=tx_info["source_id"]).first()
            if not existing_tx:
                branch = branches[tx_info["branch_code"]]
                customer = customers[tx_info["cust_code"]]

                # Calculate total amount
                total_amount = sum(line["qty"] * line["price"] for line in tx_info["lines"])

                transaction = Transaction(
                    source_transaction_id=tx_info["source_id"],
                    branch_id=branch.id,
                    customer_id=customer.id,
                    transaction_time=datetime.utcnow() - timedelta(hours=len(tx_specs)),
                    status="completed",
                    payment_method="UPI",
                    currency="INR",
                    total_amount=total_amount
                )
                db.add(transaction)
                db.flush()

                # Add sales lines for this transaction
                for idx, line_info in enumerate(tx_info["lines"], start=1):
                    product = products[line_info["sku"]]
                    net_revenue = line_info["qty"] * line_info["price"]
                    
                    sale_line = Sale(
                        transaction_id=transaction.id,
                        product_id=product.id,
                        line_number=idx,
                        quantity=line_info["qty"],
                        unit_price=line_info["price"],
                        discount_amount=Decimal("0.00"),
                        tax_amount=Decimal("0.00"),
                        net_revenue=net_revenue,
                        source_line_id=f"{tx_info['source_id']}-L{idx}"
                    )
                    db.add(sale_line)

                print(f"  + Created Transaction {tx_info['source_id']} with {len(tx_info['lines'])} sales lines.")

        db.commit()
        print("✅ Database seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    db = SessionLocal()
    seed_database(db)