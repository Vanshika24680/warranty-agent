
import sqlite3
from pathlib import Path
from datetime import date
from calendar import monthrange

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "warranty.db"


def add_months(start_date, months):
    """Calculate warranty expiry using calendar months."""
    year = start_date.year + (start_date.month - 1 + months) // 12
    month = (start_date.month - 1 + months) % 12 + 1
    day = min(start_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def check_warranty(brand, model):
    """Retrieve product information and check warranty status."""

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT product_id, brand, model,
                   purchase_date, warranty_months
            FROM products
            WHERE LOWER(brand) = LOWER(?)
              AND LOWER(model) LIKE LOWER(?)
            """,
            (brand, f"%{model}%")
        ).fetchall()

    if not rows:
        return {
            "status": "NOT_FOUND",
            "message": "No matching registered product found."
        }

    if len(rows) > 1:
        return {
            "status": "MULTIPLE_MATCHES",
            "message": "Multiple purchases match. Select a product ID.",
            "product_ids": [row["product_id"] for row in rows]
        }

    product = rows[0]
    purchase_date = date.fromisoformat(product["purchase_date"])

    expiry_date = add_months(
        purchase_date,
        product["warranty_months"]
    )

    today = date.today()
    is_active = today <= expiry_date

    return {
        "status": "ACTIVE" if is_active else "EXPIRED",
        "product_id": product["product_id"],
        "brand": product["brand"],
        "model": product["model"],
        "purchase_date": str(purchase_date),
        "expiry_date": str(expiry_date),
        "days_remaining": max((expiry_date - today).days, 0)
    }

def check_warranty_by_id(product_id):
    """Check warranty for one uniquely identified product."""

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        product = conn.execute(
            """
            SELECT product_id, brand, model,
                   purchase_date, warranty_months
            FROM products
            WHERE product_id = ?
            """,
            (product_id,)
        ).fetchone()

    if product is None:
        return {
            "status": "NOT_FOUND",
            "message": f"Product ID {product_id} does not exist."
        }

    purchase_date = date.fromisoformat(product["purchase_date"])
    expiry_date = add_months(
        purchase_date,
        product["warranty_months"]
    )

    is_active = date.today() <= expiry_date

    return {
        "status": "ACTIVE" if is_active else "EXPIRED",
        "product_id": product["product_id"],
        "brand": product["brand"],
        "model": product["model"],
        "purchase_date": str(purchase_date),
        "expiry_date": str(expiry_date),
        "days_remaining": max(
            (expiry_date - date.today()).days, 0
        )
    }



if __name__ == "__main__":
    import json

    print("TEST 1: Search by brand and model")
    print(json.dumps(
        check_warranty("HP", "Pavilion 15"),
        indent=4
    ))

    print("\nTEST 2: Resolve using product ID 15")
    print(json.dumps(
        check_warranty_by_id(15),
        indent=4
    ))

    print("\nTEST 3: Invalid product ID")
    print(json.dumps(
        check_warranty_by_id(99999),
        indent=4
    ))

