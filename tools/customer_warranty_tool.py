
from datetime import date
from calendar import monthrange


def add_months(start_date, months):
    """Add calendar months without creating invalid dates."""
    month_index = start_date.month - 1 + months
    year = start_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def assess_customer_warranty(purchase_date, warranty_months):
    """
    Estimate warranty coverage using customer-provided information.

    This does not verify manufacturer registration, exclusions,
    invoice authenticity, or claim approval.
    """
    if not purchase_date or warranty_months is None:
        return {
            "status": "NEEDS_PURCHASE_DETAILS",
            "message": "Purchase date and warranty duration are required."
        }

    try:
        purchased = date.fromisoformat(str(purchase_date))
        months = int(warranty_months)

        if months <= 0 or months > 120:
            raise ValueError("Invalid warranty duration")

        if purchased > date.today():
            raise ValueError("Purchase date cannot be in the future")

        expiry = add_months(purchased, months)
        days_remaining = (expiry - date.today()).days

        return {
            "status": (
                "ESTIMATED_ACTIVE"
                if days_remaining >= 0
                else "ESTIMATED_EXPIRED"
            ),
            "purchase_date": purchased.isoformat(),
            "estimated_expiry": expiry.isoformat(),
            "days_remaining": days_remaining,
            "verification": "CUSTOMER_PROVIDED_INFORMATION",
            "disclaimer": (
                "Estimated coverage only. Manufacturer terms, "
                "invoice validity and claim eligibility are not verified."
            )
        }

    except (ValueError, TypeError, OverflowError) as error:
        return {
            "status": "INVALID_INPUT",
            "message": str(error)
        }


if __name__ == "__main__":
    print(
        assess_customer_warranty(
            purchase_date="2026-02-15",
            warranty_months=12
        )
    )
