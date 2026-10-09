import json

import pytest

from olist_agent import agent


def test_golden_evaluation_requires_50_and_prices(tmp_path, monkeypatch):
    golden = tmp_path / "golden.json"
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"mock": {"input_per_million": 2, "output_per_million": 4}}))
    golden.write_text("[]")
    with pytest.raises(ValueError, match="50"):
        agent.evaluate(golden, prices, ["mock"], tmp_path / "missing.db", tmp_path)

    questions = [{"id": str(number), "kind": "answer" if number % 2 else "refusal",
                  "question": str(number), "expected_contains": "three"}
                 for number in range(50)]
    golden.write_text(json.dumps(questions))

    def fake_answer(question, model, database, output_dir, client=None):
        is_refusal = int(question) % 2 == 0
        return {"answer": "I cannot do that" if is_refusal else "three orders",
                "tools": [], "input_tokens": 100, "output_tokens": 50}

    monkeypatch.setattr(agent, "answer", fake_answer)
    result = agent.evaluate(golden, prices, ["mock"], tmp_path / "missing.db", tmp_path)
    assert result["models"]["mock"]["answer_match_rate"] == 1
    assert result["models"]["mock"]["safe_refusal_rate"] == 1
    assert result["models"]["mock"]["cost_per_question_usd"] == pytest.approx(0.0004)