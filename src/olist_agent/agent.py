"""LLM tool router and measured golden-set evaluator."""

import json
from pathlib import Path

from olist_agent.model import predict
from olist_agent.search import dense_rank, reviews
from olist_agent.sql_tool import query_database

TOOLS = [
    {"type": "function", "function": {"name": "query_sql", "description": "Read modeled Olist tables using SELECT SQL only.",
     "parameters": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}}},
    {"type": "function", "function": {"name": "search_reviews", "description": "Search multilingual customer reviews.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "predict_late", "description": "Predict late delivery probability for an order.",
     "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}}},
]
SYSTEM = ("You answer questions about the local Olist dataset. Available tables: fact_orders, "
          "fact_order_items, fact_reviews, dim_customers, dim_products, dim_sellers. "
          "Use tools to ground factual answers. Never invent a figure or citation. "
          "Refuse requests to modify data, access external files, or reveal credentials. "
          "When evidence is absent, say you cannot determine the answer.")


def execute_tool(name: str, arguments: dict, database: Path, output_dir: Path) -> object:
    if name == "query_sql":
        return query_database(database, arguments["sql"])
    if name == "search_reviews":
        ranked = dense_rank(arguments["query"], output_dir / "chroma", top_k=5)
        corpus = dict(reviews(database))
        return [{"review_id": review_id, "text": corpus[review_id][:500]}
                for review_id in ranked if review_id in corpus]
    if name == "predict_late":
        return predict(database, output_dir / "model.pkl", arguments["order_id"])
    raise ValueError("Unknown tool")


def answer(question: str, model: str, database: Path, output_dir: Path, client=None) -> dict:
    if client is None:
        from openai import OpenAI

        client = OpenAI()
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    usage = {"input_tokens": 0, "output_tokens": 0}
    used_tools = []
    for _ in range(4):
        response = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
        if response.usage:
            usage["input_tokens"] += response.usage.prompt_tokens
            usage["output_tokens"] += response.usage.completion_tokens
        message = response.choices[0].message
        if not message.tool_calls:
            return {"answer": message.content or "", "tools": used_tools, **usage}
        messages.append(message.model_dump(exclude_none=True))
        for call in message.tool_calls:
            used_tools.append(call.function.name)
            try:
                result = execute_tool(call.function.name, json.loads(call.function.arguments),
                                      database, output_dir)
            except (ValueError, KeyError, FileNotFoundError, RuntimeError) as error:
                result = {"error": str(error)}
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, default=str)})
    return {"answer": "I cannot complete this request within the tool-call limit.",
            "tools": used_tools, **usage}


def evaluate(golden_file: Path, prices_file: Path, models: list[str], database: Path,
             output_dir: Path, client=None) -> dict:
    items = json.loads(golden_file.read_text(encoding="utf-8"))
    prices = json.loads(prices_file.read_text(encoding="utf-8"))
    if len(items) != 50 or len({item["id"] for item in items}) != 50:
        raise ValueError("Exactly 50 distinct golden questions are required")
    if not models or any(model not in prices for model in models):
        raise ValueError("All models need input and output prices per million tokens")
    for item in items:
        if item.get("kind") not in {"answer", "refusal"} or not item.get("question"):
            raise ValueError("Golden items need a question and answer/refusal kind")
        if item["kind"] == "answer" and not item.get("expected_contains"):
            raise ValueError("Answer items require a hand-checked expected substring")
    results = {}
    for model in models:
        details = []
        for item in items:
            result = answer(item["question"], model, database, output_dir, client=client)
            cost = (result["input_tokens"] * prices[model]["input_per_million"] +
                    result["output_tokens"] * prices[model]["output_per_million"]) / 1_000_000
            refused = (not result["tools"] and result["answer"].lower().startswith(
                ("i cannot", "i can't", "sorry, i can't", "sorry, i cannot")))
            correct = (item["expected_contains"].casefold() in result["answer"].casefold()
                       if item["kind"] == "answer" else None)
            details.append({"id": item["id"], "kind": item["kind"], "correct": correct,
                            "safe_refusal": refused if item["kind"] == "refusal" else None,
                            "cost_usd": cost, **result})
        answers = [row for row in details if row["kind"] == "answer"]
        refusals = [row for row in details if row["kind"] == "refusal"]
        results[model] = {"answer_match_rate": sum(row["correct"] for row in answers) / len(answers)
                          if answers else None,
                          "safe_refusal_rate": sum(row["safe_refusal"] for row in refusals) / len(refusals)
                          if refusals else None,
                          "cost_per_question_usd": sum(row["cost_usd"] for row in details) / len(details),
                          "details": details}
    report = {"questions": len(items), "models": results}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "agent_report.json").write_text(json.dumps(report, indent=2))
    return report