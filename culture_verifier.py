import os
import json

from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict

from RAG.evidence_pack import (
    EvidencePackOutput,
    ClaimEvidencePack
)


# =========================================================
# Environment
# =========================================================

load_dotenv()


OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)


if not OPENAI_API_KEY:

    raise ValueError(
        "OPENAI_API_KEY was not found in the .env file."
    )


client = OpenAI(
    api_key=OPENAI_API_KEY
)


MODEL_NAME = "gpt-5.6-luna"

# Verification keeps a small amount of reasoning while avoiding expensive depth.
REASONING_EFFORT = "low"
MAX_OUTPUT_TOKENS_PER_CLAIM = 900
MAX_BATCH_OUTPUT_TOKENS = 4200


# =========================================================
# Verification Models
# =========================================================

class ClaimVerification(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    claim: str

    verdict: Literal[
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "UNSUPPORTED",
        "CONFLICTING",
        "INSUFFICIENT"
    ]

    reason: str

    supported_parts: list[str]

    unsupported_parts: list[str]

    recommendation: str


class CultureVerificationOutput(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    verifications: list[ClaimVerification]


# =========================================================
# Prepare Evidence
# =========================================================

def prepare_evidence_text(
    pack: ClaimEvidencePack,
    max_evidence: int = 3
) -> str:

    """
    Convert retrieved evidence into compact text
    for cultural verification.
    """

    if not pack.evidence:

        return "NO EVIDENCE RETRIEVED"


    evidence_blocks = []


    for index, item in enumerate(
        pack.evidence[:max_evidence],
        start=1
    ):

        # Keep token usage controlled.
        evidence_text = item.text[:1200]


        block = f"""
EVIDENCE {index}

Source:
{item.source_name}

Organization:
{item.organization}

Trust Tier:
{item.trust_tier}

Category:
{item.category}

URL:
{item.source_url}

Evidence Text:
{evidence_text}
"""


        evidence_blocks.append(
            block
        )


    return "\n".join(
        evidence_blocks
    )


# =========================================================
# Verify One Claim
# =========================================================

def verify_claim(
    pack: ClaimEvidencePack
) -> ClaimVerification:

    """
    Verify ONE cultural claim using ONLY
    the evidence retrieved by GameHive.
    """

    schema = (
        ClaimVerification
        .model_json_schema()
    )


    evidence_text = prepare_evidence_text(
        pack
    )


    # =====================================================
    # System Prompt
    # =====================================================

    system_prompt = """
You are the Cultural Evidence Verification Agent
inside GameHive.

Your responsibility is to evaluate ONE cultural,
historical, geographical, archaeological,
architectural, or heritage claim.

You must use ONLY the evidence supplied by GameHive.

Do NOT use outside knowledge.

Do NOT fill missing information using your
training knowledge.

Do NOT assume that a claim is correct merely because
the retrieved source is authoritative.

A UNESCO or government source can still be irrelevant
to the specific claim.


=====================================================
VERDICTS
=====================================================

Use exactly ONE of these verdicts:


SUPPORTED

The supplied evidence directly establishes all
important factual parts of the claim.


PARTIALLY_SUPPORTED

The evidence establishes some important factual parts,
but one or more meaningful parts remain unverified.


UNSUPPORTED

Use only when the supplied evidence directly indicates
that the claim is false or materially inaccurate.


CONFLICTING

Use when the supplied evidence contains meaningful
contradictory information about the claim.


INSUFFICIENT

The evidence does not provide enough relevant
information to establish or reject the claim.


=====================================================
STRICT VERIFICATION RULES
=====================================================

1. Source authority is NOT proof by itself.

2. Retrieval similarity is NOT proof.

3. Retrieval score is NOT a truth score.

4. Similar subject matter is not sufficient evidence.

5. Geographic claims require geographic evidence.

6. Historical claims require historical evidence.

7. Architectural claims require architectural evidence.

8. Cultural practices must be directly connected
   to the people, place, or tradition stated.

9. Do not combine evidence from unrelated regions
   to manufacture support.

10. Do not infer a specific Asir tradition from
    evidence about Al-Ahsa, Hima, Jeddah, or another
    unrelated region.

11. If only one meaningful portion of a compound
    claim is supported, use PARTIALLY_SUPPORTED.

12. Fictional gameplay mechanics must not be treated
    as authentic cultural practices.

13. If evidence confirms the existence of ancient
    inscriptions but does not confirm that they were
    used as alignment puzzles, the puzzle portion is
    unsupported.

14. If evidence discusses coastal heritage but does
    not mention fishermen, do not infer fishermen.

15. If evidence discusses mountains but does not
    mention terraced farming, do not infer terraces.

16. If the evidence does not directly answer the
    claim, use INSUFFICIENT.

17. Be conservative.

18. Never invent evidence.

19. Never use outside knowledge.


=====================================================
OUTPUT FIELDS
=====================================================

supported_parts:

Return only the factual portions directly supported
by the supplied evidence.

If none are established, return an empty list.


unsupported_parts:

Return factual portions that remain unsupported,
unverified, or contradicted.

Do not call something false unless the evidence
actually contradicts it.


recommendation:

Return one short GameHive action.

Preferred values include:

KEEP

REVISE

MARK AS FICTIONAL

FIND BETTER EVIDENCE

REMOVE CULTURAL CLAIM

HUMAN REVIEW
"""


    # =====================================================
    # User Prompt
    # =====================================================

    user_prompt = f"""
CLAIM TO VERIFY:

{pack.claim}


CLAIM TYPE:

{pack.claim_type}


SOURCE AREA:

{pack.source_area}


RETRIEVED EVIDENCE:

{evidence_text}


TASK:

Verify the claim using ONLY the supplied evidence.

Do not use external knowledge.

Return the structured cultural verification result.
"""


    # =====================================================
    # OpenAI Structured Response
    # =====================================================

    response = client.responses.create(

        model=MODEL_NAME,

        reasoning={
            "effort": REASONING_EFFORT
        },

        max_output_tokens=MAX_OUTPUT_TOKENS_PER_CLAIM,

        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": system_prompt
                    }
                ]
            },

            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": user_prompt
                    }
                ]
            }
        ],

        text={
            "format": {

                "type": "json_schema",

                "name":
                    "claim_verification",

                "schema":
                    schema,

                "strict":
                    True
            }
        },

        store=False
    )


    # =====================================================
    # Parse Output
    # =====================================================

    raw_output = response.output_text


    if not raw_output:

        raise RuntimeError(
            "OpenAI returned an empty "
            "Culture Verifier response."
        )


    try:

        data = json.loads(
            raw_output
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            "Culture Verifier returned invalid JSON."
        ) from error


    return ClaimVerification(
        **data
    )


# =========================================================
# Verify All Claims
# =========================================================

def verify_all_claims(
    evidence_packs: EvidencePackOutput
) -> CultureVerificationOutput:
    """
    Verify all cultural claims in ONE structured OpenAI request.

    Previous behavior:
        1 API call per claim.

    New behavior:
        all claims + their evidence -> 1 API call.

    If the batch response is malformed or returns the wrong
    number of items, GameHive safely falls back to the original
    single-claim verifier.
    """

    total_claims = len(
        evidence_packs.claim_packs
    )

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE CULTURAL VERIFIER"
    )

    print(
        "================================="
    )

    print(
        "Provider: OpenAI"
    )

    print(
        f"Model: {MODEL_NAME}"
    )

    print(
        f"Claims to verify: {total_claims}"
    )


    if total_claims == 0:

        return CultureVerificationOutput(
            verifications=[]
        )


    # -----------------------------------------------------
    # Build one compact batch.
    # -----------------------------------------------------

    batch_items = []

    for index, pack in enumerate(
        evidence_packs.claim_packs,
        start=1
    ):

        batch_items.append(
            {
                "index": index,
                "claim": pack.claim,
                "claim_type": pack.claim_type,
                "source_area": pack.source_area,
                "evidence": prepare_evidence_text(
                    pack,
                    max_evidence=3
                )
            }
        )


    batch_text = json.dumps(
        batch_items,
        ensure_ascii=False,
        indent=2
    )


    schema = (
        CultureVerificationOutput
        .model_json_schema()
    )


    system_prompt = """
You are the Cultural Evidence Verification Agent
inside GameHive.

You will receive MULTIPLE independent cultural claims.

Verify EVERY claim using ONLY the evidence supplied
for that same claim.

Do NOT use outside knowledge.
Do NOT move evidence from one claim to another.
Do NOT infer facts from source authority alone.

For each claim use exactly one verdict:

SUPPORTED
PARTIALLY_SUPPORTED
UNSUPPORTED
CONFLICTING
INSUFFICIENT

Rules:

- SUPPORTED means all important factual parts are
  directly established by the supplied evidence.

- PARTIALLY_SUPPORTED means some meaningful parts
  are established but others remain unverified.

- UNSUPPORTED means the supplied evidence directly
  indicates that the claim is false or materially
  inaccurate.

- CONFLICTING means supplied evidence meaningfully
  contradicts itself about the claim.

- INSUFFICIENT means the supplied evidence does not
  establish or reject the claim.

Be conservative.

Never invent evidence.
Never use outside knowledge.
Preserve the input claim text.
Return one verification for every input claim,
in exactly the same order.

recommendation should be one short GameHive action:
KEEP
REVISE
MARK AS FICTIONAL
FIND BETTER EVIDENCE
REMOVE CULTURAL CLAIM
HUMAN REVIEW
"""


    user_prompt = f"""
CLAIMS AND THEIR RETRIEVED EVIDENCE:

{batch_text}


TASK:

Verify every claim using ONLY the evidence attached
to that claim.

Return exactly {total_claims} verification objects
in the same order.
"""


    try:

        print(
            "\nBatch verifying all cultural claims "
            "in one OpenAI request..."
        )


        response = client.responses.create(

            model=MODEL_NAME,

            reasoning={
                "effort": REASONING_EFFORT
            },

            max_output_tokens=(
                min(
                    MAX_BATCH_OUTPUT_TOKENS,
                    max(
                        1400,
                        total_claims
                        * MAX_OUTPUT_TOKENS_PER_CLAIM
                    )
                )
            ),

            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": system_prompt
                        }
                    ]
                },

                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_prompt
                        }
                    ]
                }
            ],

            text={
                "format": {

                    "type": "json_schema",

                    "name":
                        "culture_verification_batch",

                    "schema":
                        schema,

                    "strict":
                        True
                }
            },

            store=False
        )


        raw_output = response.output_text


        if not raw_output:

            raise RuntimeError(
                "OpenAI returned an empty "
                "batch Culture Verifier response."
            )


        data = json.loads(
            raw_output
        )


        result = CultureVerificationOutput(
            **data
        )


        if len(
            result.verifications
        ) != total_claims:

            raise RuntimeError(
                "Culture verifier batch count mismatch."
            )


        # Never allow the model to rewrite the original claim.
        normalized = []

        for pack, verification in zip(
            evidence_packs.claim_packs,
            result.verifications
        ):

            normalized.append(
                verification.model_copy(
                    update={
                        "claim": pack.claim
                    }
                )
            )


        output = CultureVerificationOutput(
            verifications=normalized
        )


        for index, verification in enumerate(
            output.verifications,
            start=1
        ):

            print(
                f"Claim {index}/{total_claims}: "
                f"{verification.verdict}"
            )


        return output


    except Exception as batch_error:

        print(
            "\nBatch verification fallback activated."
        )

        print(
            "Reason:",
            str(batch_error)[:300]
        )

        print(
            "Falling back to single-claim verification."
        )


        results = []


        for index, pack in enumerate(
            evidence_packs.claim_packs,
            start=1
        ):

            print(
                f"\nVerifying cultural claim "
                f"{index}/{total_claims}..."
            )


            verification = verify_claim(
                pack
            )


            results.append(
                verification
            )


            print(
                f"Verdict: "
                f"{verification.verdict}"
            )


        return CultureVerificationOutput(
            verifications=results
        )


# =========================================================
# Print Results
# =========================================================

def print_verification_results(
    output: CultureVerificationOutput
):

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE CULTURAL VERIFICATION"
    )

    print(
        "================================="
    )


    supported_count = 0
    partial_count = 0
    unsupported_count = 0
    conflicting_count = 0
    insufficient_count = 0


    for index, result in enumerate(
        output.verifications,
        start=1
    ):

        print(
            f"\nCLAIM {index}"
        )


        print(
            f"Claim: {result.claim}"
        )


        print(
            f"Verdict: {result.verdict}"
        )


        print(
            f"Reason: {result.reason}"
        )


        # -------------------------------------------------
        # Supported Parts
        # -------------------------------------------------

        print(
            "\nSupported Parts:"
        )


        if result.supported_parts:

            for item in result.supported_parts:

                print(
                    "-",
                    item
                )

        else:

            print(
                "- None"
            )


        # -------------------------------------------------
        # Unsupported Parts
        # -------------------------------------------------

        print(
            "\nUnsupported / Unverified Parts:"
        )


        if result.unsupported_parts:

            for item in result.unsupported_parts:

                print(
                    "-",
                    item
                )

        else:

            print(
                "- None"
            )


        # -------------------------------------------------
        # Recommendation
        # -------------------------------------------------

        print(
            f"\nRecommendation: "
            f"{result.recommendation}"
        )


        print(
            "-" * 60
        )


        # -------------------------------------------------
        # Statistics
        # -------------------------------------------------

        if result.verdict == "SUPPORTED":

            supported_count += 1


        elif result.verdict == "PARTIALLY_SUPPORTED":

            partial_count += 1


        elif result.verdict == "UNSUPPORTED":

            unsupported_count += 1


        elif result.verdict == "CONFLICTING":

            conflicting_count += 1


        elif result.verdict == "INSUFFICIENT":

            insufficient_count += 1


    # =====================================================
    # Summary
    # =====================================================

    print(
        "\n================================="
    )

    print(
        "CULTURAL VERIFICATION SUMMARY"
    )

    print(
        "================================="
    )


    print(
        f"SUPPORTED: "
        f"{supported_count}"
    )


    print(
        f"PARTIALLY SUPPORTED: "
        f"{partial_count}"
    )


    print(
        f"UNSUPPORTED: "
        f"{unsupported_count}"
    )


    print(
        f"CONFLICTING: "
        f"{conflicting_count}"
    )


    print(
        f"INSUFFICIENT: "
        f"{insufficient_count}"
    )


    print(
        f"TOTAL CLAIMS: "
        f"{len(output.verifications)}"
    )