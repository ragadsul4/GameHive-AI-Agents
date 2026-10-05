from pydantic import BaseModel, ConfigDict

from agents.claim_extractor import (
    ClaimExtractionOutput,
    CulturalClaim
)

from RAG.reranker import (
    rerank_culture_evidence
)


# =========================================================
# Evidence Models
# =========================================================

class EvidenceItem(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    text: str
    source_name: str
    organization: str
    source_url: str
    category: str
    trust_tier: int
    reranker_score: float


class ClaimEvidencePack(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    claim: str
    claim_type: str
    source_area: str

    evidence: list[EvidenceItem]

    unique_sources: int

    evidence_coverage: str


class EvidencePackOutput(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    claim_packs: list[ClaimEvidencePack]


# =========================================================
# Evidence Coverage
# =========================================================

def calculate_evidence_coverage(
    evidence_items: list[EvidenceItem]
) -> str:
    """
    Measures evidence coverage.

    IMPORTANT:
    This is NOT confidence and does NOT mean
    the claim is true.

    It only describes how much authoritative
    evidence was retrieved.
    """

    if not evidence_items:

        return "INSUFFICIENT"

    unique_sources = {
        item.source_name
        for item in evidence_items
    }

    tier_one_sources = {
        item.source_name
        for item in evidence_items
        if item.trust_tier == 1
    }

    if len(tier_one_sources) >= 2:

        return "STRONG"

    if len(tier_one_sources) == 1:

        return "MODERATE"

    if len(unique_sources) >= 1:

        return "WEAK"

    return "INSUFFICIENT"


# =========================================================
# Build One Claim Pack
# =========================================================

def build_claim_evidence_pack(
    claim: CulturalClaim,
    top_k: int = 5
) -> ClaimEvidencePack:

    results = rerank_culture_evidence(
        query=claim.claim,
        candidate_count=10,
        top_k=top_k
    )

    evidence_items = []

    seen_sources = set()

    for result in results:

        metadata = result[
            "metadata"
        ]

        source_key = (
            metadata[
                "source_id"
            ],
            metadata[
                "source_url"
            ]
        )

        # Avoid returning many chunks
        # from exactly the same source.
        if source_key in seen_sources:
            continue

        seen_sources.add(
            source_key
        )

        evidence_items.append(
            EvidenceItem(

                text=result[
                    "text"
                ],

                source_name=metadata[
                    "source_name"
                ],

                organization=metadata[
                    "organization"
                ],

                source_url=metadata[
                    "source_url"
                ],

                category=metadata[
                    "category"
                ],

                trust_tier=int(
                    metadata[
                        "trust_tier"
                    ]
                ),

                reranker_score=float(
                    result[
                        "reranker_score"
                    ]
                )
            )
        )

    evidence_coverage = (
        calculate_evidence_coverage(
            evidence_items
        )
    )

    return ClaimEvidencePack(

        claim=claim.claim,

        claim_type=claim.claim_type,

        source_area=claim.source_area,

        evidence=evidence_items,

        unique_sources=len(
            evidence_items
        ),

        evidence_coverage=(
            evidence_coverage
        )
    )


# =========================================================
# Build All Evidence Packs
# =========================================================

def build_evidence_packs(
    claims: ClaimExtractionOutput
) -> EvidencePackOutput:

    packs = []

    for claim in claims.claims:

        if not claim.requires_verification:
            continue

        pack = build_claim_evidence_pack(
            claim
        )

        packs.append(
            pack
        )

    return EvidencePackOutput(
        claim_packs=packs
    )


# =========================================================
# Print Helper
# =========================================================

def print_evidence_packs(
    output: EvidencePackOutput
):

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE CULTURAL EVIDENCE PACKS"
    )

    print(
        "================================="
    )

    for index, pack in enumerate(
        output.claim_packs,
        start=1
    ):

        print(
            f"\nCLAIM {index}"
        )

        print(
            f"Claim: {pack.claim}"
        )

        print(
            f"Type: {pack.claim_type}"
        )

        print(
            f"Source Area: "
            f"{pack.source_area}"
        )

        print(
            f"Evidence Coverage: "
            f"{pack.evidence_coverage}"
        )

        print(
            f"Unique Sources: "
            f"{pack.unique_sources}"
        )

        if not pack.evidence:

            print(
                "\nNo evidence retrieved."
            )

            continue

        for evidence_index, evidence in enumerate(
            pack.evidence,
            start=1
        ):

            print(
                f"\n  EVIDENCE "
                f"{evidence_index}"
            )

            print(
                f"  Source: "
                f"{evidence.source_name}"
            )

            print(
                f"  Organization: "
                f"{evidence.organization}"
            )

            print(
                f"  Trust Tier: "
                f"{evidence.trust_tier}"
            )

            print(
                f"  Category: "
                f"{evidence.category}"
            )

            print(
                f"  URL: "
                f"{evidence.source_url}"
            )

            print(
                "  Text:"
            )

            print(
                "  "
                + evidence.text[:700]
            )
