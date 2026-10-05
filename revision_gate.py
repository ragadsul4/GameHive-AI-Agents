from typing import Literal

from pydantic import BaseModel, ConfigDict

from agents.culture_verifier import (
    CultureVerificationOutput
)


# =========================================================
# Revision Decision Model
# =========================================================

class RevisionDecision(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    claim: str

    verdict: str

    action: Literal[
        "KEEP",
        "REVISE",
        "MARK_AS_FICTIONAL_OR_REMOVE",
        "RETRY_EVIDENCE",
        "HUMAN_REVIEW"
    ]

    target_agent: Literal[
        "story_agent",
        "gameplay_agent",
        "level_design_agent",
        "none"
    ]

    requires_revision: bool

    requires_evidence_retry: bool

    requires_human_review: bool

    reason: str


class RevisionGateOutput(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    decisions: list[RevisionDecision]


# =========================================================
# Target Agent Router
# =========================================================

def get_target_agent(
    source_area: str
) -> str:
    """
    Route a failed claim back to the agent
    responsible for the original content.
    """

    mapping = {
        "story": "story_agent",
        "gameplay": "gameplay_agent",
        "level_design": "level_design_agent"
    }

    return mapping.get(
        source_area,
        "none"
    )


# =========================================================
# Decision Policy
# =========================================================

def decide_revision_action(
    verdict: str,
    retry_already_attempted: bool = False
):
    """
    Determine the next action based on
    cultural verification verdict.
    """

    # -----------------------------------------------------
    # Fully Supported
    # -----------------------------------------------------

    if verdict == "SUPPORTED":

        return {
            "action": "KEEP",
            "requires_revision": False,
            "requires_evidence_retry": False,
            "requires_human_review": False
        }


    # -----------------------------------------------------
    # Partially Supported
    # -----------------------------------------------------

    if verdict == "PARTIALLY_SUPPORTED":

        return {
            "action": "REVISE",
            "requires_revision": True,
            "requires_evidence_retry": False,
            "requires_human_review": False
        }


    # -----------------------------------------------------
    # Unsupported / Contradicted
    # -----------------------------------------------------

    if verdict == "UNSUPPORTED":

        return {
            "action": "MARK_AS_FICTIONAL_OR_REMOVE",
            "requires_revision": True,
            "requires_evidence_retry": False,
            "requires_human_review": False
        }


    # -----------------------------------------------------
    # Insufficient Evidence
    # -----------------------------------------------------

    if verdict == "INSUFFICIENT":

        # First failure:
        # search for better evidence before changing content.
        if not retry_already_attempted:

            return {
                "action": "RETRY_EVIDENCE",
                "requires_revision": False,
                "requires_evidence_retry": True,
                "requires_human_review": False
            }

        # Evidence retry already happened,
        # but evidence is still insufficient.
        # The original content should now be revised.
        return {
            "action": "REVISE",
            "requires_revision": True,
            "requires_evidence_retry": False,
            "requires_human_review": False
        }


    # -----------------------------------------------------
    # Conflicting Evidence
    # -----------------------------------------------------

    if verdict == "CONFLICTING":

        return {
            "action": "HUMAN_REVIEW",
            "requires_revision": False,
            "requires_evidence_retry": False,
            "requires_human_review": True
        }


    # -----------------------------------------------------
    # Unknown Verdict Safety Fallback
    # -----------------------------------------------------

    return {
        "action": "HUMAN_REVIEW",
        "requires_revision": False,
        "requires_evidence_retry": False,
        "requires_human_review": True
    }


# =========================================================
# Run Revision Gate
# =========================================================

def run_revision_gate(
    verification_results: CultureVerificationOutput,
    evidence_packs,
    retried_claims=None
) -> RevisionGateOutput:
    """
    Convert verification verdicts into
    workflow routing decisions.
    """

    if retried_claims is None:

        retried_claims = []


    retried_claim_set = set(
        retried_claims
    )


    decisions = []


    for verification, pack in zip(
        verification_results.verifications,
        evidence_packs.claim_packs
    ):

        # -------------------------------------------------
        # Detect Whether Evidence Retry Already Happened
        # -------------------------------------------------

        retry_already_attempted = (
            verification.claim
            in retried_claim_set
        )


        # -------------------------------------------------
        # Apply Decision Policy
        # -------------------------------------------------

        policy = decide_revision_action(
            verdict=verification.verdict,
            retry_already_attempted=retry_already_attempted
        )


        # -------------------------------------------------
        # Route Only Actual Revisions
        # -------------------------------------------------

        if policy["requires_revision"]:

            target_agent = get_target_agent(
                pack.source_area
            )

        else:

            target_agent = "none"


        # -------------------------------------------------
        # Build Decision
        # -------------------------------------------------

        decision = RevisionDecision(

            claim=verification.claim,

            verdict=verification.verdict,

            action=policy[
                "action"
            ],

            target_agent=target_agent,

            requires_revision=policy[
                "requires_revision"
            ],

            requires_evidence_retry=policy[
                "requires_evidence_retry"
            ],

            requires_human_review=policy[
                "requires_human_review"
            ],

            reason=verification.reason
        )


        decisions.append(
            decision
        )


    return RevisionGateOutput(
        decisions=decisions
    )


# =========================================================
# Print Revision Gate
# =========================================================

def print_revision_gate(
    output: RevisionGateOutput
):
    """
    Print detailed routing decisions
    and final workflow summary.
    """

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE REVISION GATE"
    )

    print(
        "================================="
    )


    # =====================================================
    # Counters
    # =====================================================

    keep_count = 0

    revision_count = 0

    retry_count = 0

    human_review_count = 0


    # =====================================================
    # Individual Decisions
    # =====================================================

    for index, decision in enumerate(
        output.decisions,
        start=1
    ):

        print(
            f"\nDECISION {index}"
        )


        print(
            f"Claim: "
            f"{decision.claim}"
        )


        print(
            f"Verdict: "
            f"{decision.verdict}"
        )


        print(
            f"Action: "
            f"{decision.action}"
        )


        print(
            f"Target Agent: "
            f"{decision.target_agent}"
        )


        print(
            f"Requires Revision: "
            f"{decision.requires_revision}"
        )


        print(
            f"Requires Evidence Retry: "
            f"{decision.requires_evidence_retry}"
        )


        print(
            f"Human Review: "
            f"{decision.requires_human_review}"
        )


        print(
            f"Reason: "
            f"{decision.reason}"
        )


        print(
            "-" * 60
        )


        # -------------------------------------------------
        # Count Final Actions
        # -------------------------------------------------

        if decision.action == "KEEP":

            keep_count += 1


        if decision.requires_revision:

            revision_count += 1


        if decision.requires_evidence_retry:

            retry_count += 1


        if decision.requires_human_review:

            human_review_count += 1


    # =====================================================
    # Final Summary
    # =====================================================

    print(
        "\n================================="
    )

    print(
        "REVISION GATE SUMMARY"
    )

    print(
        "================================="
    )


    print(
        f"Keep: "
        f"{keep_count}"
    )


    print(
        f"Needs Revision: "
        f"{revision_count}"
    )


    print(
        f"Evidence Retry: "
        f"{retry_count}"
    )


    print(
        f"Needs Human Review: "
        f"{human_review_count}"
    )


    print(
        f"Total Decisions: "
        f"{len(output.decisions)}"
    )