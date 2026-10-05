from pydantic import BaseModel, ConfigDict

from RAG.reranker import (
    rerank_culture_evidence
)

from RAG.evidence_pack import (
    EvidenceItem,
    ClaimEvidencePack,
    EvidencePackOutput,
    calculate_evidence_coverage
)

from agents.culture_verifier import (
    ClaimVerification,
    CultureVerificationOutput,
    verify_claim
)


# =========================================================
# Retry Models
# =========================================================

class EvidenceRetryResult(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    claim: str

    previous_verdict: str

    new_verdict: str

    queries_tried: list[str]

    unique_sources_after_retry: int


class EvidenceRetryOutput(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    updated_verification_results: CultureVerificationOutput

    retried_claims: list[str]

    retry_results: list[EvidenceRetryResult]


# =========================================================
# Build Better Queries
# =========================================================

def build_retry_queries(
    pack: ClaimEvidencePack,
    verification: ClaimVerification
) -> list[str]:

    """
    Generate more focused search queries.

    Instead of simply repeating the original claim,
    GameHive searches specifically for the parts that
    the verifier could not establish.
    """

    queries = []

    # Original claim
    queries.append(
        pack.claim
    )

    # Search unsupported parts individually
    for unsupported_part in (
        verification.unsupported_parts[:2]
    ):

        queries.append(
            unsupported_part
        )

        queries.append(
            f"{unsupported_part} "
            f"Saudi Arabia "
            f"{pack.claim_type}"
        )

    # Remove duplicates while preserving order
    unique_queries = []

    seen = set()

    for query in queries:

        normalized = query.strip().lower()

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        unique_queries.append(
            query.strip()
        )

    # Keep retry controlled
    return unique_queries[:4]


# =========================================================
# Convert Retriever Result
# =========================================================

def result_to_evidence_item(
    result
) -> EvidenceItem:

    metadata = result[
        "metadata"
    ]

    return EvidenceItem(

        text=result[
            "text"
        ],

        source_name=metadata.get(
            "source_name",
            "Unknown"
        ),

        organization=metadata.get(
            "organization",
            "Unknown"
        ),

        source_url=metadata.get(
            "source_url",
            ""
        ),

        category=metadata.get(
            "category",
            "unknown"
        ),

        trust_tier=int(
            metadata.get(
                "trust_tier",
                99
            )
        ),

        reranker_score=float(
            result.get(
                "reranker_score",
                0.0
            )
        )
    )


# =========================================================
# Retry One Claim
# =========================================================

def retry_claim_evidence(
    pack: ClaimEvidencePack,
    verification: ClaimVerification
):

    queries = build_retry_queries(
        pack,
        verification
    )

    # Keep original evidence too
    evidence_by_source = {}

    for item in pack.evidence:

        key = (
            item.source_url
            or item.source_name
        )

        evidence_by_source[
            key
        ] = item

    # -----------------------------------------------------
    # Search Again Using Focused Queries
    # -----------------------------------------------------

    for query in queries:

        print(
            f"  Retry query: {query}"
        )

        results = rerank_culture_evidence(
            query=query,
            candidate_count=12,
            top_k=5
        )

        for result in results:

            item = result_to_evidence_item(
                result
            )

            key = (
                item.source_url
                or item.source_name
            )

            # Keep the highest-scoring chunk
            # from each unique source
            existing = evidence_by_source.get(
                key
            )

            if (
                existing is None
                or
                item.reranker_score
                >
                existing.reranker_score
            ):

                evidence_by_source[
                    key
                ] = item

    # -----------------------------------------------------
    # Rank Merged Evidence
    # -----------------------------------------------------

    merged_evidence = list(
        evidence_by_source.values()
    )

    merged_evidence.sort(
        key=lambda item: item.reranker_score,
        reverse=True
    )

    # Limit evidence sent to next verification stage
    merged_evidence = (
        merged_evidence[:5]
    )

    updated_pack = ClaimEvidencePack(

        claim=pack.claim,

        claim_type=pack.claim_type,

        source_area=pack.source_area,

        evidence=merged_evidence,

        unique_sources=len(
            merged_evidence
        ),

        evidence_coverage=(
            calculate_evidence_coverage(
                merged_evidence
            )
        )
    )

    return (
        updated_pack,
        queries
    )


# =========================================================
# Retry All Insufficient Claims
# =========================================================

def retry_insufficient_evidence(
    evidence_packs: EvidencePackOutput,
    verification_results: CultureVerificationOutput
) -> EvidenceRetryOutput:

    updated_verifications = list(
        verification_results.verifications
    )

    retried_claims = []

    retry_results = []

    total = len(
        evidence_packs.claim_packs
    )

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE EVIDENCE RETRY"
    )

    print(
        "================================="
    )

    for index, (
        pack,
        verification
    ) in enumerate(

        zip(
            evidence_packs.claim_packs,
            verification_results.verifications
        ),

        start=1
    ):

        if (
            verification.verdict
            != "INSUFFICIENT"
        ):
            continue

        print(
            f"\nRetrying evidence for "
            f"claim {index}/{total}"
        )

        print(
            f"Claim: {pack.claim}"
        )

        previous_verdict = (
            verification.verdict
        )

        updated_pack, queries = (
            retry_claim_evidence(
                pack,
                verification
            )
        )

        # Verify again using improved evidence
        new_verification = verify_claim(
            updated_pack
        )

        updated_verifications[
            index - 1
        ] = new_verification

        retried_claims.append(
            pack.claim
        )

        retry_results.append(
            EvidenceRetryResult(

                claim=pack.claim,

                previous_verdict=(
                    previous_verdict
                ),

                new_verdict=(
                    new_verification.verdict
                ),

                queries_tried=queries,

                unique_sources_after_retry=(
                    updated_pack.unique_sources
                )
            )
        )

        print(
            f"New verdict: "
            f"{new_verification.verdict}"
        )

    return EvidenceRetryOutput(

        updated_verification_results=(
            CultureVerificationOutput(
                verifications=(
                    updated_verifications
                )
            )
        ),

        retried_claims=(
            retried_claims
        ),

        retry_results=(
            retry_results
        )
    )


# =========================================================
# Print Retry Summary
# =========================================================

def print_evidence_retry(
    output: EvidenceRetryOutput
):

    print(
        "\n================================="
    )

    print(
        "EVIDENCE RETRY SUMMARY"
    )

    print(
        "================================="
    )

    if not output.retry_results:

        print(
            "No evidence retries were required."
        )

        return

    for index, result in enumerate(
        output.retry_results,
        start=1
    ):

        print(
            f"\nRETRY {index}"
        )

        print(
            f"Claim: {result.claim}"
        )

        print(
            f"Previous Verdict: "
            f"{result.previous_verdict}"
        )

        print(
            f"New Verdict: "
            f"{result.new_verdict}"
        )

        print(
            f"Unique Sources: "
            f"{result.unique_sources_after_retry}"
        )

        print(
            "Queries Tried:"
        )

        for query in result.queries_tried:

            print(
                "-",
                query
            )