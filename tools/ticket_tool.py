
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "database" / "warranty.db"


def create_support_ticket(customer_name, brand, product, issue, request_id=None):
    """Create an application-managed support ticket."""

    if not all([
        str(customer_name).strip(),
        str(brand).strip(),
        str(product).strip(),
        str(issue).strip()
    ]):
        return {
            "status": "VALIDATION_FAILED",
            "message": "All fields are required."
        }

    ticket_id = "TKT-" + uuid.uuid4().hex[:10].upper()
    created_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_support_tickets (
                ticket_id TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL,
                brand TEXT NOT NULL,
                product TEXT NOT NULL,
                issue TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        
        # Add an idempotency key without deleting existing tickets.
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(app_support_tickets)"
            )
        }

        if "request_id" not in columns:
            conn.execute(
                "ALTER TABLE app_support_tickets "
                "ADD COLUMN request_id TEXT"
            )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_app_ticket_request_id
            ON app_support_tickets(request_id)
            """
        )

        if request_id:
            existing = conn.execute(
                """
                SELECT ticket_id, status
                FROM app_support_tickets
                WHERE request_id = ?
                """,
                (request_id,)
            ).fetchone()

            if existing:
                return {
                    "status": "SUCCESS",
                    "ticket_id": existing[0],
                    "ticket_status": existing[1],
                    "duplicate_prevented": True,
                    "message": "Existing ticket reused."
                }


       
        conn.execute(
            """
            INSERT INTO app_support_tickets
            (ticket_id, customer_name, brand, product,
             issue, status, created_at, request_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                customer_name,
                brand,
                product,
                issue,
                "OPEN",
                created_at,
                request_id
            )
        )


    return {
        "status": "SUCCESS",
        "ticket_id": ticket_id,
        "ticket_status": "OPEN",
        "created_at": created_at,
        "message": "Support ticket saved in application database."
    }


if __name__ == "__main__":
    result = create_support_ticket(
        customer_name="Demo Customer",
        brand="HP",
        product="Pavilion laptop",
        issue="Overheating"
    )
    print(result)



def update_ticket_status(ticket_id, new_status):
    """Update an existing application support ticket."""

    allowed_statuses = {"OPEN", "IN_PROGRESS", "RESOLVED"}

    if new_status not in allowed_statuses:
        return {
            "status": "INVALID_STATUS",
            "message": "Unsupported ticket status."
        }

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            UPDATE app_support_tickets
            SET status = ?
            WHERE ticket_id = ?
            """,
            (new_status, ticket_id)
        )

        if cursor.rowcount == 0:
            return {
                "status": "NOT_FOUND",
                "message": "Ticket ID does not exist."
            }

        conn.commit()

    return {
        "status": "SUCCESS",
        "ticket_id": ticket_id,
        "new_status": new_status
    }
