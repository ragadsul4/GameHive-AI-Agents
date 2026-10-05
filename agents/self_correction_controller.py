from typing import Literal

from pydantic import BaseModel, ConfigDict

from state import GameState

from agents.claim_extractor import (
    ClaimExtractionOutput,
    extract_cultural_claims
)

from RAG.evidence_pack import (
    EvidencePackOutput,
    build_evidence_packs
)

from agents.culture_verifier import (
    CultureVerificationOutput,
    verify_all_claims
)

from RAG.evidence_retry import (
    EvidenceRetryOutput,
    retry_insufficient_evidence
)

from agents.revision_gate import (
    RevisionDecision,
    RevisionGateOutput,
    run_revision_gate
)

from agents.targeted_revision import (
    apply_targeted_revisions
)


# =========================================================
# Configuration
# =========================================================

MAX_REVISION_ROUNDS = 2


# =========================================================
# Round Report
# =========================================================

class CorrectionRoundReport(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    round_number: int

    claims_count: int

    supported_count: int

    partially_supported_count: int

    unsupported_count: int

    insufficient_count: int

    conflicting_count: int

    revisions_required: int

    human_reviews_required: int

    revised_agents: list[str]


# =========================================================
# Full Self-Correction Report
# =========================================================

class SelfCorrectionReport(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    rounds_completed: int

    max_revision_rounds: int

    has_verifiable_claims: bool

    approved: bool

    final_status: Literal[
        "APPROVED",
        "HUMAN_REVIEW_REQUIRED",
        "NO_VERIFIABLE_CLAIMS"
    ]

    final_keep_count: int

    final_human_review_count: int

    unresolved_claims: list[str]

    rounds: list[CorrectionRoundReport]


# =========================================================
# Count Verification Verdicts
# =========================================================

def count_verdicts(
    verification_results: CultureVerificationOutput
):

    counts = {
        "SUPPORTED": 0,
        "PARTIALLY_SUPPORTED": 0,
        "UNSUPPORTED": 0,
        "INSUFFICIENT": 0,
        "CONFLICTING": 0
    }

    for item in verification_results.verifications:

        if item.verdict in counts:

            counts[
                item.verdict
            ] += 1

    return counts


# =========================================================
# Check Whether Revision Is Required
# =========================================================

def has_revision_work(
    revision_gate: RevisionGateOutput
) -> bool:

    for decision in revision_gate.decisions:

        if decision.requires_revision:

            return True

    return False


# =========================================================
# Escalate Remaining Problems
# =========================================================

def escalate_remaining_to_human_review(
    revision_gate: RevisionGateOutput
) -> RevisionGateOutput:
    """
    If automatic correction rounds are exhausted,
    unresolved automatic revisions are escalated
    to human review instead of creating an
    infinite correction loop.
    """

    final_decisions = []


    for decision in revision_gate.decisions:

        # -------------------------------------------------
        # Already resolved
        # -------------------------------------------------

        if (
            decision.action == "KEEP"
            and not decision.requires_human_review
        ):

            final_decisions.append(
                decision
            )

            continue


        # -------------------------------------------------
        # Already requires human review
        # -------------------------------------------------

        if decision.requires_human_review:

            final_decisions.append(
                decision
            )

            continue


        # -------------------------------------------------
        # Still unresolved after automatic correction
        # -------------------------------------------------

        if (
            decision.requires_revision
            or decision.requires_evidence_retry
        ):

            escalated = RevisionDecision(

                claim=decision.claim,

                verdict=decision.verdict,

                action="HUMAN_REVIEW",

                target_agent="none",

                requires_revision=False,

                requires_evidence_retry=False,

                requires_human_review=True,

                reason=(
                    decision.reason
                    + " Maximum automatic correction "
                    + "rounds were reached. "
                    + "The unresolved claim has been "
                    + "escalated to human review."
                )
            )

            final_decisions.append(
                escalated
            )

            continue


        final_decisions.append(
            decision
        )


    return RevisionGateOutput(
        decisions=final_decisions
    )


# =========================================================
# Determine Final Status
# =========================================================

def determine_final_status(
    revision_gate: RevisionGateOutput
):

    """
    Distinguish between:

    1. No claims existed to verify.
    2. All claims were successfully verified.
    3. Some claims still require human review.
    """

    decisions = revision_gate.decisions


    # -----------------------------------------------------
    # No cultural claims existed
    # -----------------------------------------------------

    if len(decisions) == 0:

        return {
            "has_verifiable_claims": False,
            "approved": False,
            "final_status": "NO_VERIFIABLE_CLAIMS"
        }


    # -----------------------------------------------------
    # Human review remains
    # -----------------------------------------------------

    has_human_review = any(

        decision.requires_human_review

        for decision in decisions
    )


    if has_human_review:

        return {
            "has_verifiable_claims": True,
            "approved": False,
            "final_status": "HUMAN_REVIEW_REQUIRED"
        }


    # -----------------------------------------------------
    # All claims successfully resolved
    # -----------------------------------------------------

    all_keep = all(

        decision.action == "KEEP"

        for decision in decisions
    )


    if all_keep:

        return {
            "has_verifiable_claims": True,
            "approved": True,
            "final_status": "APPROVED"
        }


    # -----------------------------------------------------
    # Safety Fallback
    # -----------------------------------------------------

    return {
        "has_verifiable_claims": True,
        "approved": False,
        "final_status": "HUMAN_REVIEW_REQUIRED"
    }


# =========================================================
# Run Closed-Loop Self Correction
# =========================================================

def run_self_correction(
    state: GameState,
    initial_claims: ClaimExtractionOutput,
    initial_evidence_packs: EvidencePackOutput,
    initial_verification_results: CultureVerificationOutput,
    initial_retry_results: EvidenceRetryOutput,
    initial_revision_decisions: RevisionGateOutput,
    max_revision_rounds: int = MAX_REVISION_ROUNDS
):
    """
    Closed-loop correction controller.

    Flow:

    Revision Gate
        ↓
    Targeted Revision
        ↓
    Claim Re-Extraction
        ↓
    Evidence Retrieval
        ↓
    Verification
        ↓
    Evidence Retry
        ↓
    Revision Gate Again

    The loop stops when:

    1. No automatic revisions remain.
    OR
    2. Maximum revision rounds are reached.

    Important:

    No cultural claims is NOT treated as APPROVED.
    It receives its own final status:
    NO_VERIFIABLE_CLAIMS.
    """

    current_claims = (
        initial_claims
    )

    current_evidence_packs = (
        initial_evidence_packs
    )

    current_verification_results = (
        initial_verification_results
    )

    current_retry_results = (
        initial_retry_results
    )

    current_revision_decisions = (
        initial_revision_decisions
    )


    round_reports = []

    rounds_completed = 0


    # =====================================================
    # Handle Zero-Claim Case
    # =====================================================

    if len(current_claims.claims) == 0:

        print(
            "\nNo verifiable cultural claims "
            "were detected."
        )

        print(
            "The cultural verification pipeline "
            "will not mark this run as APPROVED "
            "because no claim was actually verified."
        )


    # =====================================================
    # Correction Loop
    # =====================================================

    for round_number in range(
        1,
        max_revision_rounds + 1
    ):

        # -------------------------------------------------
        # Stop If No Revision Is Required
        # -------------------------------------------------

        if not has_revision_work(
            current_revision_decisions
        ):

            if len(
                current_revision_decisions.decisions
            ) > 0:

                print(
                    "\nNo additional automatic "
                    "revision is required."
                )

            break


        print(
            "\n================================="
        )

        print(
            f"SELF-CORRECTION ROUND {round_number}"
        )

        print(
            "================================="
        )


        # -------------------------------------------------
        # Targeted Revision
        # -------------------------------------------------

        state, revision_report = (
            apply_targeted_revisions(

                state,

                current_revision_decisions,

                current_verification_results,

                current_evidence_packs
            )
        )


        # -------------------------------------------------
        # Re-Extract Claims
        # -------------------------------------------------

        current_claims = (
            extract_cultural_claims(
                state
            )
        )


        print(
            "Claims after revision:",
            len(
                current_claims.claims
            )
        )


        # -------------------------------------------------
        # Retrieve New Evidence
        # -------------------------------------------------

        current_evidence_packs = (
            build_evidence_packs(
                current_claims
            )
        )


        print(
            "Evidence packs:",
            len(
                current_evidence_packs.claim_packs
            )
        )


        # -------------------------------------------------
        # Verify Again
        # -------------------------------------------------

        current_verification_results = (
            verify_all_claims(
                current_evidence_packs
            )
        )


        # -------------------------------------------------
        # Evidence Retry
        # -------------------------------------------------

        current_retry_results = (
            retry_insufficient_evidence(

                current_evidence_packs,

                current_verification_results
            )
        )


        current_verification_results = (
            current_retry_results
            .updated_verification_results
        )


        # -------------------------------------------------
        # Run Revision Gate Again
        # -------------------------------------------------

        current_revision_decisions = (
            run_revision_gate(

                current_verification_results,

                current_evidence_packs,

                retried_claims=(
                    current_retry_results
                    .retried_claims
                )
            )
        )


        # -------------------------------------------------
        # Build Round Metrics
        # -------------------------------------------------

        verdict_counts = count_verdicts(
            current_verification_results
        )


        revisions_required = sum(

            1

            for decision
            in current_revision_decisions.decisions

            if decision.requires_revision
        )


        human_reviews_required = sum(

            1

            for decision
            in current_revision_decisions.decisions

            if decision.requires_human_review
        )


        round_report = CorrectionRoundReport(

            round_number=round_number,

            claims_count=len(
                current_claims.claims
            ),

            supported_count=(
                verdict_counts[
                    "SUPPORTED"
                ]
            ),

            partially_supported_count=(
                verdict_counts[
                    "PARTIALLY_SUPPORTED"
                ]
            ),

            unsupported_count=(
                verdict_counts[
                    "UNSUPPORTED"
                ]
            ),

            insufficient_count=(
                verdict_counts[
                    "INSUFFICIENT"
                ]
            ),

            conflicting_count=(
                verdict_counts[
                    "CONFLICTING"
                ]
            ),

            revisions_required=(
                revisions_required
            ),

            human_reviews_required=(
                human_reviews_required
            ),

            revised_agents=(
                revision_report.revised_agents
            )
        )


        round_reports.append(
            round_report
        )


        rounds_completed += 1


        # -------------------------------------------------
        # Round Summary
        # -------------------------------------------------

        print(
            "\nRound Summary:"
        )


        print(
            "SUPPORTED:",
            verdict_counts[
                "SUPPORTED"
            ]
        )


        print(
            "PARTIALLY_SUPPORTED:",
            verdict_counts[
                "PARTIALLY_SUPPORTED"
            ]
        )


        print(
            "UNSUPPORTED:",
            verdict_counts[
                "UNSUPPORTED"
            ]
        )


        print(
            "INSUFFICIENT:",
            verdict_counts[
                "INSUFFICIENT"
            ]
        )


        print(
            "CONFLICTING:",
            verdict_counts[
                "CONFLICTING"
            ]
        )


        print(
            "Still Needs Revision:",
            revisions_required
        )


        # -------------------------------------------------
        # Successful Early Exit
        # -------------------------------------------------

        if not has_revision_work(
            current_revision_decisions
        ):

            if len(
                current_revision_decisions.decisions
            ) > 0:

                print(
                    "\nAutomatic correction "
                    "converged successfully."
                )

            break


    # =====================================================
    # Maximum-Round Safety Gate
    # =====================================================

    if has_revision_work(
        current_revision_decisions
    ):

        print(
            "\nMaximum automatic correction "
            "rounds reached."
        )

        print(
            "Remaining unresolved claims "
            "will be escalated to human review."
        )


        current_revision_decisions = (
            escalate_remaining_to_human_review(
                current_revision_decisions
            )
        )


    # =====================================================
    # Final Counts
    # =====================================================

    final_keep_count = sum(

        1

        for decision
        in current_revision_decisions.decisions

        if decision.action == "KEEP"
    )


    final_human_review_count = sum(

        1

        for decision
        in current_revision_decisions.decisions

        if decision.requires_human_review
    )


    unresolved_claims = [

        decision.claim

        for decision
        in current_revision_decisions.decisions

        if decision.requires_human_review
    ]


    # =====================================================
    # Determine Final Status
    # =====================================================

    status_result = determine_final_status(
        current_revision_decisions
    )


    has_verifiable_claims = (
        status_result[
            "has_verifiable_claims"
        ]
    )


    approved = (
        status_result[
            "approved"
        ]
    )


    final_status = (
        status_result[
            "final_status"
        ]
    )


    # =====================================================
    # Final Report
    # =====================================================

    final_report = SelfCorrectionReport(

        rounds_completed=(
            rounds_completed
        ),

        max_revision_rounds=(
            max_revision_rounds
        ),

        has_verifiable_claims=(
            has_verifiable_claims
        ),

        approved=(
            approved
        ),

        final_status=(
            final_status
        ),

        final_keep_count=(
            final_keep_count
        ),

        final_human_review_count=(
            final_human_review_count
        ),

        unresolved_claims=(
            unresolved_claims
        ),

        rounds=(
            round_reports
        )
    )


    return (
        state,
        current_claims,
        current_evidence_packs,
        current_verification_results,
        current_retry_results,
        current_revision_decisions,
        final_report
    )


# =========================================================
# Print Final Controller Report
# =========================================================

def print_self_correction_report(
    report: SelfCorrectionReport
):

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE SELF-CORRECTION REPORT"
    )

    print(
        "================================="
    )


    print(
        "Rounds Completed:",
        report.rounds_completed
    )


    print(
        "Maximum Rounds:",
        report.max_revision_rounds
    )


    print(
        "Verifiable Claims:",
        (
            "YES"
            if report.has_verifiable_claims
            else "NO"
        )
    )


    print(
        "Final KEEP:",
        report.final_keep_count
    )


    print(
        "Human Review:",
        report.final_human_review_count
    )


    # =====================================================
    # Final Status
    # =====================================================

    if (
        report.final_status
        == "APPROVED"
    ):

        print(
            "\nFINAL STATUS: APPROVED"
        )

        print(
            "All verifiable cultural claims "
            "passed the final approval gate."
        )


    elif (
        report.final_status
        == "NO_VERIFIABLE_CLAIMS"
    ):

        print(
            "\nFINAL STATUS: "
            "NO VERIFIABLE CULTURAL CLAIMS"
        )

        print(
            "No cultural claims requiring "
            "verification were detected."
        )

        print(
            "This run is not classified as "
            "APPROVED because no cultural "
            "claim was actually verified."
        )


    else:

        print(
            "\nFINAL STATUS: "
            "HUMAN REVIEW REQUIRED"
        )

        print(
            "One or more cultural claims "
            "remain unresolved after the "
            "automatic correction process."
        )


    # =====================================================
    # Round History
    # =====================================================

    if report.rounds:

        print(
            "\nCorrection History:"
        )


        for round_report in report.rounds:

            print(
                "\n---------------------------------"
            )


            print(
                "Round:",
                round_report.round_number
            )


            print(
                "Claims:",
                round_report.claims_count
            )


            print(
                "SUPPORTED:",
                round_report.supported_count
            )


            print(
                "PARTIALLY_SUPPORTED:",
                round_report.partially_supported_count
            )


            print(
                "UNSUPPORTED:",
                round_report.unsupported_count
            )


            print(
                "INSUFFICIENT:",
                round_report.insufficient_count
            )


            print(
                "CONFLICTING:",
                round_report.conflicting_count
            )


            print(
                "Needs Revision:",
                round_report.revisions_required
            )


            print(
                "Human Review:",
                round_report.human_reviews_required
            )


            print(
                "Revised Agents:",
                round_report.revised_agents
            )


    # =====================================================
    # Remaining Claims
    # =====================================================

    if report.unresolved_claims:

        print(
            "\nClaims Requiring Human Review:"
        )


        for claim in report.unresolved_claims:

            print(
                "-",
                claim
            )
