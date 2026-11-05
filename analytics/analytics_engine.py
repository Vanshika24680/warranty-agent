
import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "warranty.db"


def load_data():
    with sqlite3.connect(DB_PATH) as conn:
        products = pd.read_sql_query(
            "SELECT * FROM products", conn
        )
        claims = pd.read_sql_query(
            "SELECT * FROM claims", conn
        )
        tickets = pd.read_sql_query(
            "SELECT * FROM support_tickets", conn
        )

    return products, claims, tickets


def generate_analytics():
    products, claims, tickets = load_data()

    total_products = len(products)
    total_claims = len(claims)
    total_tickets = len(tickets)

    approved_claims = (
        claims["status"] == "Approved"
    ).sum()

    resolved_tickets = (
        tickets["status"] == "Closed"
    ).sum()

    approval_rate = (
        approved_claims / total_claims * 100
        if total_claims else 0
    )

    resolution_rate = (
        resolved_tickets / total_tickets * 100
        if total_tickets else 0
    )

    # Identify the most common reported problems
    common_issues = (
        claims["issue_type"]
        .value_counts()
        .reset_index()
    )
    common_issues.columns = ["Issue", "Count"]

    # Brand-wise number of claims
    brand_claims = (
        claims.merge(
            products[["product_id", "brand"]],
            on="product_id",
            how="left"
        )
        .groupby("brand")
        .size()
        .reset_index(name="Claims")
        .sort_values("Claims", ascending=False)
    )

    # Claim rates adjusted for registered product counts
    brand_totals = (
        products.groupby("brand")
        .size()
        .reset_index(name="Registered_Products")
    )

    brand_claim_rates = brand_totals.merge(
        brand_claims,
        on="brand",
        how="left"
    ).fillna({"Claims": 0})

    brand_claim_rates["Claims_Per_100_Products"] = (
        brand_claim_rates["Claims"]
        / brand_claim_rates["Registered_Products"]
        * 100
    )

    print("\n===== WARRANTY INTELLIGENCE ANALYTICS =====")
    print(f"Total Products: {total_products}")
    print(f"Total Claims: {total_claims}")
    print(f"Total Support Tickets: {total_tickets}")
    print(f"Claim Approval Rate: {approval_rate:.2f}%")
    print(f"Ticket Resolution Rate: {resolution_rate:.2f}%")

    print("\nMost Common Issues:")
    print(common_issues.to_string(index=False))

    print("\nBrand-wise Claim Rates:")
    print(
        brand_claim_rates.sort_values(
            "Claims_Per_100_Products",
            ascending=False
        ).to_string(index=False)
    )

    return {
        "total_products": total_products,
        "total_claims": total_claims,
        "total_tickets": total_tickets,
        "approval_rate": approval_rate,
        "resolution_rate": resolution_rate,
        "common_issues": common_issues,
        "brand_claim_rates": brand_claim_rates,
    }


if __name__ == "__main__":
    generate_analytics()
