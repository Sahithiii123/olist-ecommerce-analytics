"""Review retrieval and hand-labelled precision-at-five evaluation."""

import json
from functools import lru_cache
from pathlib import Path

import duckdb
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


@lru_cache(maxsize=2)
def embedding_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def reviews(database: Path) -> list[tuple[str, str]]:
    with duckdb.connect(str(database), read_only=True) as con:
        rows = con.execute("""
            SELECT review_id, COALESCE(review_comment_title, '') || ' ' || review_comment_message
            FROM fact_reviews WHERE review_comment_message IS NOT NULL
              AND length(trim(review_comment_message)) > 0
            QUALIFY row_number() OVER (PARTITION BY review_id ORDER BY order_id) = 1
            ORDER BY review_id
        """).fetchall()
    return [(str(review_id), text.strip()) for review_id, text in rows]


def index(database: Path, index_dir: Path, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2") -> dict:
    import chromadb

    corpus = reviews(database)
    if not corpus:
        raise ValueError("No nonempty reviews found")
    index_dir.mkdir(parents=True, exist_ok=True)
    model = embedding_model(model_name)
    client = chromadb.PersistentClient(path=str(index_dir))
    collection = client.get_or_create_collection("reviews", metadata={"hnsw:space": "cosine"})
    for offset in range(0, len(corpus), 256):
        batch = corpus[offset:offset + 256]
        embeddings = model.encode([text for _, text in batch], normalize_embeddings=True)
        collection.upsert(ids=[review_id for review_id, _ in batch],
                          documents=[text for _, text in batch], embeddings=embeddings.tolist())
    metadata = {"model": model_name, "reviews": len(corpus)}
    (index_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return metadata


def tfidf_rank(query: str, corpus: list[tuple[str, str]], top_k: int = 20) -> list[str]:
    vectorizer = TfidfVectorizer(strip_accents="unicode", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform([text for _, text in corpus])
    scores = (matrix @ vectorizer.transform([query]).T).toarray().ravel()
    return [corpus[position][0] for position in np.argsort(-scores, kind="stable")[:top_k]]


def dense_rank(query: str, index_dir: Path, top_k: int = 20) -> list[str]:
    import chromadb

    metadata = json.loads((index_dir / "metadata.json").read_text())
    model = embedding_model(metadata["model"])
    collection = chromadb.PersistentClient(path=str(index_dir)).get_collection("reviews")
    embedding = model.encode([query], normalize_embeddings=True).tolist()
    return collection.query(query_embeddings=embedding,
                            n_results=min(top_k, collection.count()))["ids"][0]


def hybrid_rank(sparse: list[str], dense: list[str], top_k: int = 5) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in (sparse, dense):
        for position, review_id in enumerate(ranking):
            scores[review_id] = scores.get(review_id, 0) + 1 / (60 + position + 1)
    return sorted(scores, key=lambda review_id: (-scores[review_id], review_id))[:top_k]


def validate_labels(labels: list[dict], corpus_ids: set[str]) -> None:
    if len(labels) != 30 or len({item["query"] for item in labels}) != 30:
        raise ValueError("Exactly 30 distinct hand-labelled queries are required")
    for item in labels:
        if not item["query"].strip() or not item["relevant_review_ids"]:
            raise ValueError("Every query needs at least one relevant review ID")
        if not set(item["relevant_review_ids"]) <= corpus_ids:
            raise ValueError("A relevance label refers to a review outside the index")


def evaluate(database: Path, index_dir: Path, labels_file: Path, output_dir: Path) -> dict:
    corpus = reviews(database)
    labels = json.loads(labels_file.read_text(encoding="utf-8"))
    validate_labels(labels, {review_id for review_id, _ in corpus})
    vectorizer = TfidfVectorizer(strip_accents="unicode", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform([text for _, text in corpus])
    scores = {method: [] for method in ("tfidf", "dense", "hybrid")}
    for item in labels:
        similarities = (matrix @ vectorizer.transform([item["query"]]).T).toarray().ravel()
        sparse = [corpus[pos][0] for pos in np.argsort(-similarities, kind="stable")[:20]]
        dense = dense_rank(item["query"], index_dir)
        relevant = set(item["relevant_review_ids"])
        for method, ranked in (("tfidf", sparse), ("dense", dense),
                               ("hybrid", hybrid_rank(sparse, dense))):
            scores[method].append(len(relevant.intersection(ranked[:5])) / 5)
    report = {"queries": 30, "precision_at_5": {key: float(np.mean(values))
                                                    for key, values in scores.items()}}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "retrieval_report.json").write_text(json.dumps(report, indent=2))
    return report