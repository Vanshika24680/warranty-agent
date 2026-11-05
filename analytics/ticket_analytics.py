
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "database" / "warranty.db"


def load_tickets():
    """Read actual tickets created through the application."""
    if not DB_PATH.exists():
        return pd.DataFrame()

    with sqlite3.connect(DB_PATH) as conn:
        try:
            df = pd.read_sql_query(
                """
                SELECT ticket_id, customer_name, brand, product,
                       issue, status, created_at
                FROM app_support_tickets
                ORDER BY created_at DESC
                """,
                conn
            )
        except pd.errors.DatabaseError:
            return pd.DataFrame()

    if not df.empty:
        df["created_at"] = pd.to_datetime(
            df["created_at"],
            errors="coerce",
            utc=True
        )
        df["brand"] = df["brand"].fillna("Unknown")
        df["status"] = df["status"].fillna("Unknown")

    return df


def get_ticket_metrics(df):
    """Calculate operational metrics from persisted tickets."""
    if df.empty:
        return {
            "total_tickets": 0,
            "open_tickets": 0,
            "resolved_tickets": 0,
            "resolution_rate": 0.0
        }

    status = df["status"].str.upper()

    total = len(df)
    resolved = int((status == "RESOLVED").sum())

    return {
        "total_tickets": total,
        "open_tickets": int((status == "OPEN").sum()),
        "resolved_tickets": resolved,
        "resolution_rate": round(resolved / total * 100, 1)
    }


if __name__ == "__main__":
    tickets = load_tickets()
    print("TICKETS LOADED:", len(tickets))
    print("METRICS:", get_ticket_metrics(tickets))
