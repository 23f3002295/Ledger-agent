
import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

with open("orders.json", encoding="utf-8") as f:
    ORDERS = json.load(f)

with open("rates.json", encoding="utf-8") as f:
    RATES = json.load(f)


def order_date(order):
    """Convert an order's timestamp to its Indian business date."""
    value = order["created_at"].replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)

    return dt.astimezone(IST).date()


def usd_amount(order):
    """Convert an order amount to USD using the supplied rates."""
    amount = Decimal(str(order["amount"]))
    rate = Decimal(str(RATES[order["currency"]]))
    return amount * rate


def money(value):
    """Round money to two decimal places."""
    return float(
        Decimal(value).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
    )


def calculate(plan):
    """
    plan example:
    {
        "metric": "revenue",
        "region": "North",
        "start_date": "2026-03-01",
        "end_date_exclusive": "2026-04-01"
    }
    """

    metric = plan.get("metric")

    supported = {
        "revenue",
        "refunds",
        "order_count",
        "customer_count",
        "units_sold",
        "product_revenue",
        "revenue_by_region",
        "top_product"
    }

    if metric not in supported:
        raise ValueError("Unsupported metric")

    start = (
        date.fromisoformat(plan["start_date"])
        if plan.get("start_date") else None
    )

    end = (
        date.fromisoformat(plan["end_date_exclusive"])
        if plan.get("end_date_exclusive") else None
    )

    filtered = []

    for order in ORDERS:
        if plan.get("region") and (
            order["region"].casefold()
            != plan["region"].casefold()
        ):
            continue

        if plan.get("product") and (
            order["product"].casefold()
            != plan["product"].casefold()
        ):
            continue

        if plan.get("customer") and (
            order["customer"].casefold()
            != plan["customer"].casefold()
        ):
            continue

        current_date = order_date(order)

        if start and current_date < start:
            continue

        if end and current_date >= end:
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

    if metric == "refunds":
        total = sum(
            (
                usd_amount(o)
                for o in filtered
                if o["status"] == "refunded"
            ),
            Decimal("0")
        )
        return money(total)

    if metric == "order_count":
        return sum(o["status"] == "paid" for o in filtered)

    if metric == "customer_count":
        return len({
            o["customer"]
            for o in filtered
            if o["status"] == "paid"
        })

    if metric == "units_sold":
        return sum(
            o["qty"] for o in filtered
            if o["status"] == "paid"
        )

    if metric == "product_revenue":
        totals = {}

        for o in filtered:
            if o["status"] == "paid":
                product = o["product"]
                totals[product] = (
                    totals.get(product, Decimal("0"))
                    + usd_amount(o)
                )

        return {
            product: money(total)
            for product, total in sorted(totals.items())
        }

    if metric == "revenue_by_region":
        totals = {}

        for o in filtered:
            if o["status"] == "paid":
                region = o["region"]
                totals[region] = (
                    totals.get(region, Decimal("0"))
                    + usd_amount(o)
                )

        return {
            region: money(total)
            for region, total in sorted(totals.items())
        }

    if metric == "top_product":
        totals = {}

        for o in filtered:
            if o["status"] == "paid":
                product = o["product"]
                totals[product] = (
                    totals.get(product, 0) + o["qty"]
                )

        if not totals:
            return None

        highest = max(totals.values())

        return [
            {"product": name, "units_sold": qty}
            for name, qty in sorted(totals.items())
            if qty == highest
        ]


if __name__ == "__main__":
    example = {
        "metric": "revenue",
        "region": "North",
        "start_date": "2026-03-01",
        "end_date_exclusive": "2026-04-01"
    }

    print("Example result:", calculate(example))
