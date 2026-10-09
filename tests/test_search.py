import pytest

from olist_agent.search import hybrid_rank, tfidf_rank, validate_labels


def test_sparse_and_hybrid_rank():
    corpus = [("1", "entrega atrasada"), ("2", "produto bom")]
    assert tfidf_rank("entrega", corpus)[0] == "1"
    assert hybrid_rank(["1", "2"], ["2", "1"]) == ["1", "2"]


def test_evaluation_needs_real_labels():
    with pytest.raises(ValueError, match="30"):
        validate_labels([{"query": "late", "relevant_review_ids": ["1"]}], {"1"})