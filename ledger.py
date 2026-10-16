
import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent

with open(BASE_DIR / "orders.json", "r", encoding="utf-8") as f:
    ORDERS = json.load(f)

with open(BASE_DIR / "rates.json", "r", encoding="utf-8") as f:
    RATES = json.load(f)

# Support either the full rates response or the rates dictionary.
if "usd_per_unit" in RATES:
    RATES = RATES["usd_per_unit"]

INDIA_TZ = ZoneInfo("Asia/Kolkata")


def order_date(order):
    """Return the order's creation date in India."""
    value = order["created_at"]
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=INDIA_TZ)

    return dt.astimezone(INDIA_TZ).date()


def usd_amount(order):
    """Convert the order amount into USD."""
    amount = Decimal(str(order["amount"]))
    rate = Decimal(str(RATES[order["currency"]]))
    return amount * rate


def money(value):
    """Round a monetary result to two decimal places."""
    return float(
        Decimal(str(value)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
    )


def current_orders(orders):
    """
    Keep the latest updated row for each order ID.
    If timestamps tie, retain the last row encountered.
    """
    latest = {}

    for order in orders:
        order_id = order["id"]
        updated = datetime.fromisoformat(
            order["updated_at"].replace("Z", "+00:00")
        )

        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=INDIA_TZ)

        if (
            order_id not in latest
            or updated >= latest[order_id][0]
        ):
            latest[order_id] = (updated, order)

    return [item[1] for item in latest.values()]


# Deduplicate once before calculating any metric.
ORDERS = current_orders(ORDERS)


def calculate(plan):
    metric = plan.get("metric")

    region = plan.get("region")
    product = plan.get("product")
    customer = plan.get("customer")
    start_date = plan.get("start_date")
    end_date_exclusive = plan.get("end_date_exclusive")

    start = date.fromisoformat(start_date) if start_date else None
    end = (
        date.fromisoformat(end_date_exclusive)
        if end_date_exclusive
        else None
    )

    filtered = []

    for order in ORDERS:
        if region and order["region"].casefold() != region.casefold():
            continue

        if product and order["product"].casefold() != product.casefold():
            continue

        if customer and order["customer"].casefold() != customer.casefold():
            continue

        created = order_date(order)

        if start and created < start:
            continue

        if end and created >= end:
            continue

        filtered.append(order)

    if metric == "revenue":
        total = sum(
            (
                usd_amount(o)
                for o in filtered
                if o["status"] == "paid"
            ),
            Decimal("0")
        )
        return money(total)

    elif metric == "refunded_order_count":
        return sum(
            1
            for o in filtered
            if o["status"] == "refunded"
        )

    elif metric == "refunds":
        total = sum(
            (
                usd_amount(o)
                for o in filtered
                if o["status"] == "refunded"
            ),
            Decimal("0")
        )
        return money(total)

    elif metric == "order_count":
        return sum(
            1 for o in filtered
            if o["status"] == "paid"
        )

    elif metric == "customer_count":
        return len({
            o["customer"]
            for o in filtered
            if o["status"] == "paid"
        })

    elif metric == "units_sold":
        return sum(
            o["qty"]
            for o in filtered
            if o["status"] == "paid"
        )

    elif metric == "product_revenue":
        totals = {}

        for o in filtered:
            if o["status"] == "paid":
                name = o["product"]
                totals[name] = (
                    totals.get(name, Decimal("0"))
                    + usd_amount(o)
                )

        return {
            name: money(total)
            for name, total in sorted(totals.items())
        }

    elif metric == "revenue_by_region":
        totals = {}

        for o in filtered:
            if o["status"] == "paid":
                name = o["region"]
                totals[name] = (
                    totals.get(name, Decimal("0"))
                    + usd_amount(o)
                )

        return {
            name: money(total)
            for name, total in sorted(totals.items())
        }

    elif metric == "top_product":
        totals = {}

        for o in filtered:
            if o["status"] == "paid":
                name = o["product"]
                totals[name] = totals.get(name, 0) + o["qty"]

        if not totals:
            return None

        highest = max(totals.values())

        return [
            {"product": name, "units_sold": qty}
            for name, qty in sorted(totals.items())
            if qty == highest
        ]

    return None


if __name__ == "__main__":
    example = {
        "metric": "revenue",
        "region": "North",
        "product": None,
        "customer": None,
        "start_date": "2026-03-01",
        "end_date_exclusive": "2026-04-01"
    }

    print("Example result:", calculate(example))

    refunded_example = {
        "metric": "refunded_order_count",
        "region": "Central",
        "product": None,
        "customer": None,
        "start_date": "2026-03-01",
        "end_date_exclusive": "2026-04-01"
    }

    print(
        "Central refunded orders in March 2026:",
        calculate(refunded_example)
    )
