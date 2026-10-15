
import json
import requests
from datetime import datetime, timezone

# Load the URLs discovered from your assignment API
with open("api_response.json", "r", encoding="utf-8") as file:
    api_data = json.load(file)

export_url = api_data["links"]["export"]
rates_url = api_data["links"]["rates"]

# Download the complete ledger export
response = requests.get(export_url, timeout=20)
response.raise_for_status()

# NDJSON: each line is a separate JSON object
orders = []

for line in response.text.splitlines():
    if line.strip():
        orders.append(json.loads(line))

print("Rows downloaded:", len(orders))

# Keep the latest version of each order ID
latest_orders = {}

def parse_timestamp(value):
    # Handle timestamps ending in Z
    value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)

    # Treat timestamps without timezone information as UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)

for order in orders:
    order_id = order["id"]

    if order_id not in latest_orders:
        latest_orders[order_id] = order
    else:
        old_time = parse_timestamp(
            latest_orders[order_id]["updated_at"]
        )
        new_time = parse_timestamp(order["updated_at"])

        if new_time > old_time:
            latest_orders[order_id] = order

orders = list(latest_orders.values())

print("Unique current orders:", len(orders))

# Download currency conversion rates
rates_response = requests.get(rates_url, timeout=10)
rates_response.raise_for_status()
rates = rates_response.json()["usd_per_unit"]

# Save the processed data
with open("orders.json", "w", encoding="utf-8") as file:
    json.dump(orders, file, indent=2, ensure_ascii=False)

with open("rates.json", "w", encoding="utf-8") as file:
    json.dump(rates, file, indent=2)

print("Currency rates:", rates)
print("Saved orders.json and rates.json")
