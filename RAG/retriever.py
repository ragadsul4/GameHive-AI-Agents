import re
from collections import defaultdict

import chromadb
import numpy as np

from rank_bm25 import BM25Okapi
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


# =========================================================
# Configuration
# =========================================================

DB_FOLDER = "chroma_db"
COLLECTION_NAME = "culture_sources"

# RRF constant
RRF_K = 60


# =========================================================
# ChromaDB
# =========================================================

embedding_function = DefaultEmbeddingFunction()

client = chromadb.PersistentClient(
    path=DB_FOLDER
)

collection = client.get_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_function
)


# =========================================================
# Tokenization
# =========================================================

def tokenize(text: str) -> list[str]:
    """
    Simple multilingual tokenizer.

    Keeps Arabic and English words and numbers.
    """

    return re.findall(
        r"\w+",
        text.lower(),
        flags=re.UNICODE
    )


# =========================================================
# Load Corpus for BM25
# =========================================================

def load_bm25_corpus():

    results = collection.get(
        include=[
            "documents",
            "metadatas"
        ]
    )

    documents = results["documents"]
    metadatas = results["metadatas"]
    ids = results["ids"]

    tokenized_documents = [
        tokenize(document)
        for document in documents
    ]

    bm25 = BM25Okapi(
        tokenized_documents
    )

    return (
        ids,
        documents,
        metadatas,
        bm25
    )


DOCUMENT_IDS, DOCUMENTS, METADATAS, BM25_INDEX = (
    load_bm25_corpus()
)


# =========================================================
# Semantic Search
# =========================================================

def semantic_search(
    query: str,
    n_results: int = 10
):

    n_results = min(
        n_results,
        collection.count()
    )

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )

    retrieved = []

    for rank, (
        doc_id,
        document,
        metadata,
        distance
    ) in enumerate(
        zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ),
        start=1
    ):

        retrieved.append(
            {
                "id": doc_id,
                "document": document,
                "metadata": metadata,
                "distance": float(distance),
                "rank": rank
            }
        )

    return retrieved


# =========================================================
# BM25 Search
# =========================================================

def bm25_search(
    query: str,
    n_results: int = 10
):

    query_tokens = tokenize(
        query
    )

    scores = BM25_INDEX.get_scores(
        query_tokens
    )

    ranked_indexes = np.argsort(
        scores
    )[::-1]

    retrieved = []

    for rank, index in enumerate(
        ranked_indexes[:n_results],
        start=1
    ):

        retrieved.append(
            {
                "id": DOCUMENT_IDS[index],
                "document": DOCUMENTS[index],
                "metadata": METADATAS[index],
                "bm25_score": float(
                    scores[index]
                ),
                "rank": rank
            }
        )

    return retrieved


# =========================================================
# Reciprocal Rank Fusion
# =========================================================

def reciprocal_rank_fusion(
    semantic_results,
    bm25_results,
    semantic_weight=1.0,
    bm25_weight=1.0
):

    fused_scores = defaultdict(
        float
    )

    result_lookup = {}

    # Semantic results
    for item in semantic_results:

        doc_id = item["id"]

        fused_scores[doc_id] += (
            semantic_weight
            / (RRF_K + item["rank"])
        )

        result_lookup[doc_id] = item

    # BM25 results
    for item in bm25_results:

        doc_id = item["id"]

        fused_scores[doc_id] += (
            bm25_weight
            / (RRF_K + item["rank"])
        )

        if doc_id not in result_lookup:
            result_lookup[doc_id] = item

    ranked_ids = sorted(
        fused_scores,
        key=fused_scores.get,
        reverse=True
    )

    fused_results = []

    for final_rank, doc_id in enumerate(
        ranked_ids,
        start=1
    ):

        original = result_lookup[
            doc_id
        ]

        fused_results.append(
            {
                "id":
                    doc_id,

                "text":
                    original["document"],

                "metadata":
                    original["metadata"],

                "rrf_score":
                    fused_scores[doc_id],

                "rank":
                    final_rank
            }
        )

    return fused_results


# =========================================================
# Main Hybrid Retriever
# =========================================================

def retrieve_culture_context(
    query: str,
    k: int = 5
):

    candidate_count = min(
        max(k * 4, 10),
        collection.count()
    )

    semantic_results = semantic_search(
        query=query,
        n_results=candidate_count
    )

    lexical_results = bm25_search(
        query=query,
        n_results=candidate_count
    )

    fused_results = reciprocal_rank_fusion(
        semantic_results,
        lexical_results
    )

    return fused_results[:k]


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    query = (
        "What cultural heritage "
        "is associated with Saudi Arabia?"
    )

    results = retrieve_culture_context(
        query=query,
        k=5
    )

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE HYBRID RAG TEST"
    )

    print(
        "================================="
    )

    print(
        f"\nQuery:\n{query}"
    )

    for index, result in enumerate(
        results,
        start=1
    ):

        metadata = result[
            "metadata"
        ]

        print(
            "\n---------------------------------"
        )

        print(
            f"RESULT {index}"
        )

        print(
            f"RRF Score: "
            f"{result['rrf_score']:.6f}"
        )

        print(
            f"Organization: "
            f"{metadata['organization']}"
        )

        print(
            f"Source: "
            f"{metadata['source_name']}"
        )

        print(
            f"Trust Tier: "
            f"{metadata['trust_tier']}"
        )

        print(
            f"URL: "
            f"{metadata['source_url']}"
        )

        print(
            "\nEvidence:"
        )

        print(
            result["text"][:700]
        )
