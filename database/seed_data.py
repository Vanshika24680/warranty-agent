
import sqlite3
from pathlib import Path
from datetime import date, timedelta
import random

DB_PATH = Path(__file__).resolve().parent / "warranty.db"

random.seed(42)

products = [
    ("HP", "Pavilion 15", "Laptop", 12),
    ("Dell", "Inspiron 15", "Laptop", 12),
    ("Lenovo", "IdeaPad Slim 3", "Laptop", 12),
    ("Samsung", "Galaxy A54", "Smartphone", 12),
    ("LG", "Smart TV 43", "Television", 24),
    ("Whirlpool", "265L Refrigerator", "Refrigerator", 12),
    ("Boat", "Airdopes 141", "Earbuds", 12),
    ("Sony", "WH-CH520", "Headphones", 12),
]

issues = [
    "Overheating",
    "Battery problem",
    "Display issue",
    "Power failure",
    "Connectivity issue",
    "Unusual noise",
]

statuses = ["Pending", "Approved", "Rejected", "Resolved"]


def seed_database():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] > 0:
        print("Sample data already exists. Skipping.")
        connection.close()
        return

    for i in range(80):
        brand, model, category, warranty_months = random.choice(products)

        purchase_date = (
            date.today() - timedelta(days=random.randint(30, 900))
        ).isoformat()

        cursor.execute("""
            INSERT INTO products
            (brand, model, category, purchase_date, warranty_months)
            VALUES (?, ?, ?, ?, ?)
        """, (brand, model, category, purchase_date, warranty_months))

        product_id = cursor.lastrowid

        # Not every product has a claim
        if random.random() < 0.65:
            issue = random.choice(issues)
            claim_date = (
                date.today() - timedelta(days=random.randint(0, 29))
            ).isoformat()
            status = random.choice(statuses)

            cursor.execute("""
                INSERT INTO claims
                (product_id, issue_type, claim_date, status)
                VALUES (?, ?, ?, ?)
            """, (product_id, issue, claim_date, status))

            cursor.execute("""
                INSERT INTO support_tickets
                (product_id, issue_description, locality, status)
                VALUES (?, ?, ?, ?)
            """, (
                product_id,
                issue,
                random.choice([
                    "Vijay Nagar",
                    "Palasia",
                    "Bhawarkuan",
                    "Rau",
                    "Rajendra Nagar",
                ]),
                "Closed" if status == "Resolved" else "Open"
            ))

    connection.commit()
    connection.close()

    print("80 sample products and associated claims/tickets added!")
    print("Note: All generated records are synthetic demonstration data.")


if __name__ == "__main__":
    seed_database()
