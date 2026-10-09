"""Command-line entry points for local, reproducible runs."""

import argparse
import json
from pathlib import Path

from olist_agent import pipeline


def main() -> None:
    parser = argparse.ArgumentParser(prog="olist")
    parser.add_argument("--data", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    actions = parser.add_subparsers(dest="action", required=True)
    for name in ("build", "flow", "benchmark", "train", "index", "search",
                 "evaluate-search", "ask", "evaluate-agent", "analyze-delivery"):
        action = actions.add_parser(name)
        if name == "analyze-delivery":
            action.add_argument("--tableau", type=Path, default=Path("tableau"))
        if name == "train":
            action.add_argument("--mlflow", action="store_true")
        if name in {"search", "ask"}:
            action.add_argument("text")
        if name == "evaluate-search":
            action.add_argument("--labels", required=True, type=Path)
        if name in {"ask", "evaluate-agent"}:
            action.add_argument("--model", action="append", required=True)
        if name == "evaluate-agent":
            action.add_argument("--golden", required=True, type=Path)
            action.add_argument("--prices", required=True, type=Path)
    args = parser.parse_args()
    database = args.output / "olist.duckdb"
    if args.action == "build":
        result = pipeline.build(args.data, args.output)
    elif args.action == "flow":
        result = pipeline.prefect_flow(args.data, args.output)
    elif args.action == "benchmark":
        result = pipeline.benchmark(args.data, args.output)
    elif args.action == "analyze-delivery":
        from olist_agent.delivery import analyze_delivery

        result = analyze_delivery(database, args.tableau)
    elif args.action == "train":
        from olist_agent.model import train

        result = train(database, args.output, args.mlflow)
    elif args.action == "index":
        from olist_agent.search import index

        result = index(database, args.output / "chroma")
    elif args.action == "search":
        from olist_agent.search import dense_rank

        result = dense_rank(args.text, args.output / "chroma", top_k=5)
    elif args.action == "evaluate-search":
        from olist_agent.search import evaluate

        result = evaluate(database, args.output / "chroma", args.labels, args.output)
    elif args.action == "ask":
        from olist_agent.agent import answer

        result = answer(args.text, args.model[0], database, args.output)
    else:
        from olist_agent.agent import evaluate

        result = evaluate(args.golden, args.prices, args.model, database, args.output)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()