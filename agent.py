
import os
import json
from flask import Flask, request, jsonify
from google import genai
from ledger import calculate
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Configure Gemini using an environment variable.
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

MODEL = "gemini-2.5-flash"

PLANNER_PROMPT = """
You convert questions about the Acme Appliances order ledger
into a JSON calculation plan.

Return ONLY a valid JSON object with these fields:
- metric
- region
- product
- customer
- start_date
- end_date_exclusive

Use null for filters that are not mentioned.

Allowed metrics:
revenue, refunds, order_count, customer_count, units_sold,
product_revenue, revenue_by_region, top_product

Rules:
1. Revenue means the sum of amounts for paid orders only.
2. Refunds means the sum of amounts for orders whose current
   status is refunded.
3. Convert questions about number of paid orders to order_count.
4. Convert questions about distinct customers to customer_count.
5. Convert questions about units sold to units_sold.
6. Use product_revenue for a breakdown of revenue by product.
7. Use revenue_by_region for a breakdown of revenue by region.
8. Use top_product for the product with the most units sold.
9. Dates must use YYYY-MM-DD format.
10. end_date_exclusive is the day AFTER the requested end date.
11. Interpret business dates using Asia/Kolkata.
12. If a question asks for a specific product, region, or customer,
    set the matching filter.
13. If no date range is specified, leave both date fields null.
14. Do not invent ledger figures or answer the question yourself.
15. If the question is unclear or unrelated to the ledger,
    return {"metric": "invalid"}.

Example question:
"What was the revenue in North during March 2026?"

Example JSON:
{
  "metric": "revenue",
  "region": "North",
  "product": null,
  "customer": null,
  "start_date": "2026-03-01",
  "end_date_exclusive": "2026-04-01"
}
"""


def make_plan(question):
    prompt = (
        PLANNER_PROMPT
        + "\n\nUser question:\n"
        + question
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json"
        }
    )

    plan = json.loads(response.text)

    if not isinstance(plan, dict):
        raise ValueError("The AI returned an invalid plan.")

    return plan


@app.get("/")
def home():
    return jsonify({
        "service": "Acme Appliances Ledger Agent",
        "status": "running"
    })


@app.post("/")
def answer_question():
    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "answer": "Please send a JSON object containing question."
            }), 400

        question = data.get("question")

        if not isinstance(question, str) or not question.strip():
            return jsonify({
                "answer": "The question field is required."
            }), 400

        if len(question) > 2000:
            return jsonify({
                "answer": "The question is too long."
            }), 400

        if not os.getenv("GEMINI_API_KEY"):
            return jsonify({
                "answer": "Server configuration error."
            }), 500

        plan = make_plan(question.strip())

        if plan.get("metric") == "invalid":
            return jsonify({
                "answer": "I can answer questions about the order ledger."
            })

        allowed_metrics = {
            "revenue",
            "refunds",
            "order_count",
            "customer_count",
            "units_sold",
            "product_revenue",
            "revenue_by_region",
            "top_product"
        }

        if plan.get("metric") not in allowed_metrics:
            return jsonify({
                "answer": "I could not interpret that ledger question."
            }), 400

        # Only accept the supported fields from the AI plan.
        safe_plan = {
            key: plan.get(key)
            for key in (
                "metric",
                "region",
                "product",
                "customer",
                "start_date",
                "end_date_exclusive"
            )
        }

        result = calculate(safe_plan)

        return jsonify({"answer": result})

    except (ValueError, KeyError, TypeError) as exc:
        app.logger.warning("Invalid question or plan: %s", exc)
        return jsonify({
            "answer": "I could not process that question."
        }), 400

    except Exception:
        app.logger.exception("Ledger Agent error")
        return jsonify({
            "answer": "The server could not process the question."
        }), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
