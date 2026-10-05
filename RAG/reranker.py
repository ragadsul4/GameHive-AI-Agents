import re

from fastembed.rerank.cross_encoder import TextCrossEncoder

from RAG.retriever import retrieve_culture_context


# =========================================================
# Configuration
# =========================================================

RERANKER_MODEL = (
    "jinaai/jina-reranker-v2-base-multilingual"
)

# Number of candidates coming from Hybrid Retrieval
CANDIDATE_COUNT = 6

# Final evidence returned after reranking
FINAL_TOP_K = 3

# Minimum amount of usable evidence
MIN_EVIDENCE_LENGTH = 80


# =========================================================
# Noise Patterns
# =========================================================

NOISE_PHRASES = [
    "Periodic Reporting Questionnaire 2008-2015",
    "Periodic Reporting Questionnaire 2018-2024",
    "Arab States, World Heritage Convention Regional Contact",
    "Arab States, World Heritage Regional page",
    "State of Conservation",
    "Properties inscribed on the World Heritage List",
    "World Heritage Fund",
    "International Assistance",
    "Privacy Notice",
    "Terms of use",
    "Sign in",
    "Login",
]


# =========================================================
# Evidence Cleaning
# =========================================================

def clean_evidence_text(text: str) -> str:
    """
    Remove website boilerplate while preserving
    useful cultural information inside the same chunk.
    """

    if not text:
        return ""

    cleaned = text

    # -----------------------------------------------------
    # Remove ESRI / WebGL browser warning
    # -----------------------------------------------------

    cleaned = re.sub(
        r"Web Browser not supported.*?"
        r"WebGL must be enable[d]?[,.]?",
        " ",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL
    )

    # -----------------------------------------------------
    # Remove known navigation / website phrases
    # -----------------------------------------------------

    for phrase in NOISE_PHRASES:

        cleaned = re.sub(
            re.escape(phrase),
            " ",
            cleaned,
            flags=re.IGNORECASE
        )

    # -----------------------------------------------------
    # Normalize whitespace
    # -----------------------------------------------------

    cleaned = re.sub(
        r"[ \t]+",
        " ",
        cleaned
    )

    cleaned = re.sub(
        r"\n\s*\n+",
        "\n",
        cleaned
    )

    cleaned = cleaned.strip()

    return cleaned


# =========================================================
# Candidate Preparation
# =========================================================

def prepare_candidates(candidates):
    """
    Clean retrieved chunks before sending them
    to the cross-encoder reranker.

    Very small / useless chunks are discarded.
    """

    prepared = []

    for candidate in candidates:

        cleaned_text = clean_evidence_text(
            candidate["text"]
        )

        if len(cleaned_text) < MIN_EVIDENCE_LENGTH:
            continue

        cleaned_candidate = (
            candidate.copy()
        )

        # Preserve original text for debugging / audit
        cleaned_candidate[
            "original_text"
        ] = candidate["text"]

        # Reranker will use cleaned evidence
        cleaned_candidate[
            "text"
        ] = cleaned_text

        prepared.append(
            cleaned_candidate
        )

    return prepared


# =========================================================
# Load Reranker
# =========================================================

# Lazy singleton.
# The cross-encoder is NOT loaded when GameHive starts.
# It loads only if cultural RAG actually needs reranking.
_reranker = None


def get_reranker():
    global _reranker

    if _reranker is None:

        print(
            "Loading multilingual reranker..."
        )

        _reranker = TextCrossEncoder(
            model_name=RERANKER_MODEL
        )

        print(
            "Reranker ready."
        )

    return _reranker


# =========================================================
# Main Reranking Function
# =========================================================

def rerank_culture_evidence(
    query: str,
    candidate_count: int = CANDIDATE_COUNT,
    top_k: int = FINAL_TOP_K
):
    """
    Professional second-stage retrieval:

    1. Hybrid Retrieval
       Semantic + BM25 + RRF

    2. Evidence Cleaning
       Remove website boilerplate

    3. Cross-Encoder Reranking
       Query + evidence evaluated together

    4. Return the strongest evidence
    """

    # =====================================================
    # Stage 1 — Hybrid Retrieval
    # =====================================================

    candidates = retrieve_culture_context(
        query=query,
        k=candidate_count
    )

    if not candidates:
        return []

    # =====================================================
    # Stage 2 — Evidence Cleaning
    # =====================================================

    candidates = prepare_candidates(
        candidates
    )

    if not candidates:
        return []

    # =====================================================
    # Stage 3 — Prepare Documents
    # =====================================================

    documents = [
        candidate["text"]
        for candidate in candidates
    ]

    # =====================================================
    # Stage 4 — Cross-Encoder Reranking
    # =====================================================

    active_reranker = get_reranker()

    scores = list(
        active_reranker.rerank(
            query,
            documents
        )
    )

    # =====================================================
    # Stage 5 — Attach Scores
    # =====================================================

    reranked_results = []

    for candidate, score in zip(
        candidates,
        scores
    ):

        result = candidate.copy()

        result[
            "reranker_score"
        ] = float(score)

        reranked_results.append(
            result
        )

    # =====================================================
    # Stage 6 — Sort
    # =====================================================

    reranked_results.sort(
        key=lambda item: item[
            "reranker_score"
        ],
        reverse=True
    )

    # =====================================================
    # Stage 7 — Final Top-K
    # =====================================================

    final_results = []

    for rank, item in enumerate(
        reranked_results[:top_k],
        start=1
    ):

        item[
            "final_rank"
        ] = rank

        final_results.append(
            item
        )

    return final_results


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    test_query = (
        "What evidence exists about traditional "
        "Saudi cultural heritage and practices?"
    )

    results = rerank_culture_evidence(
        query=test_query,
        candidate_count=10,
        top_k=5
    )

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE CULTURAL EVIDENCE RERANKER"
    )

    print(
        "================================="
    )

    print(
        f"\nQuery:\n{test_query}"
    )

    print(
        f"\nFinal Evidence Results: "
        f"{len(results)}"
    )

    for result in results:

        metadata = result[
            "metadata"
        ]

        print(
            "\n================================="
        )

        print(
            f"FINAL RANK: "
            f"{result['final_rank']}"
        )

        print(
            "================================="
        )

        print(
            f"Reranker Score: "
            f"{result['reranker_score']:.6f}"
        )

        print(
            f"Hybrid RRF Score: "
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
            f"Category: "
            f"{metadata['category']}"
        )

        print(
            f"URL: "
            f"{metadata['source_url']}"
        )

        print(
            "\nClean Evidence:"
        )

        print(
            result["text"][:1200]
        )
