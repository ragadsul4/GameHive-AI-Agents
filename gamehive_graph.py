from typing import TypedDict, Any
from concurrent.futures import ThreadPoolExecutor
import time

from langgraph.graph import (
    StateGraph,
    START,
    END
)

from state import GameState

from agents.story_agent import (
    story_agent
)

from agents.gameplay_agent import (
    gameplay_agent
)

from agents.level_design_agent import (
    level_design_agent
)

from agents.claim_extractor import (
    CulturalClaim,
    ClaimExtractionOutput,
    extract_cultural_claims
)

from agents.claim_scope_router import (
    ClaimScopeOutput,
    route_claim_scopes,
    get_cultural_claims,
    get_game_state_claims,
    get_fictional_claims
)

from agents.game_state_verifier import (
    GameStateVerificationOutput,
    verify_game_state_claims
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
    RevisionGateOutput,
    run_revision_gate
)

from agents.targeted_revision import (
    apply_targeted_revisions
)


# =========================================================
# Configuration
# =========================================================

DEFAULT_MAX_REVISION_ROUNDS = 2


# =========================================================
# LangGraph Shared State
# =========================================================

class GameHiveGraphState(
    TypedDict,
    total=False
):

    # -----------------------------------------------------
    # Core Game Design
    # -----------------------------------------------------

    game_state: GameState


    # -----------------------------------------------------
    # Raw Claim Extraction
    # -----------------------------------------------------

    claims: ClaimExtractionOutput


    # -----------------------------------------------------
    # Claim Scope Routing
    # -----------------------------------------------------

    scoped_claims: ClaimScopeOutput


    # -----------------------------------------------------
    # Internal Game-State Verification
    # -----------------------------------------------------

    game_state_verification_results: (
        GameStateVerificationOutput
    )


    # -----------------------------------------------------
    # Cultural RAG Pipeline
    # -----------------------------------------------------

    cultural_claims: ClaimExtractionOutput

    evidence_packs: EvidencePackOutput

    verification_results: CultureVerificationOutput

    retry_results: EvidenceRetryOutput

    revision_decisions: RevisionGateOutput


    # -----------------------------------------------------
    # Revision Control
    # -----------------------------------------------------

    revision_round: int

    max_revision_rounds: int

    had_verifiable_claims: bool

    last_revision_report: Any


    # -----------------------------------------------------
    # Final Workflow Status
    # -----------------------------------------------------

    approved: bool

    final_status: str

    requires_human_review: bool


    # -----------------------------------------------------
    # UI / Demo Observability
    # -----------------------------------------------------

    current_stage: str

    execution_trace: list[str]

    node_timings: dict[str, float]

    total_generation_seconds: float


# =========================================================
# Trace Helper
# =========================================================

def add_trace(
    state: GameHiveGraphState,
    stage: str
) -> list[str]:

    trace = list(
        state.get(
            "execution_trace",
            []
        )
    )

    trace.append(
        stage
    )

    return trace


def add_timing(
    state: GameHiveGraphState,
    stage: str,
    seconds: float
) -> dict[str, float]:

    timings = dict(
        state.get(
            "node_timings",
            {}
        )
    )

    timings[stage] = round(
        timings.get(
            stage,
            0.0
        )
        + seconds,
        3
    )

    return timings


# =========================================================
# Story Node
# =========================================================

def story_node(
    state: GameHiveGraphState
):
    print(
        "\n[LangGraph] STORY AGENT"
    )

    game_state = state[
        "game_state"
    ]

    started = time.perf_counter()

    game_state = story_agent(
        game_state
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        f"[Timing] story_agent: {elapsed:.2f}s"
    )

    return {
        "game_state": game_state,
        "node_timings": add_timing(
            state,
            "story_agent",
            elapsed
        ),
        "current_stage": "story_agent",
        "execution_trace": add_trace(
            state,
            "story_agent"
        )
    }

# =========================================================
# Gameplay Node
# =========================================================

def gameplay_node(
    state: GameHiveGraphState
):
    print(
        "\n[LangGraph] GAMEPLAY AGENT"
    )

    game_state = state[
        "game_state"
    ]

    started = time.perf_counter()

    game_state = gameplay_agent(
        game_state
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        f"[Timing] gameplay_agent: {elapsed:.2f}s"
    )

    return {
        "game_state": game_state,
        "node_timings": add_timing(
            state,
            "gameplay_agent",
            elapsed
        ),
        "current_stage": "gameplay_agent",
        "execution_trace": add_trace(
            state,
            "gameplay_agent"
        )
    }

# =========================================================
# Level Design Node
# =========================================================

def level_design_node(
    state: GameHiveGraphState
):
    print(
        "\n[LangGraph] LEVEL DESIGN AGENT"
    )

    game_state = state[
        "game_state"
    ]

    started = time.perf_counter()

    game_state = level_design_agent(
        game_state
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        f"[Timing] level_design_agent: {elapsed:.2f}s"
    )

    return {
        "game_state": game_state,
        "node_timings": add_timing(
            state,
            "level_design_agent",
            elapsed
        ),
        "current_stage": "level_design_agent",
        "execution_trace": add_trace(
            state,
            "level_design_agent"
        )
    }

# =========================================================
# Raw Claim Extraction Node
# =========================================================

def claim_extraction_node(
    state: GameHiveGraphState
):
    print(
        "\n[LangGraph] CLAIM EXTRACTION"
    )

    started = time.perf_counter()

    claims = extract_cultural_claims(
        state[
            "game_state"
        ]
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        f"[Timing] claim_extraction: {elapsed:.2f}s"
    )

    claim_count = len(
        claims.claims
    )

    print(
        "Raw Claims Found:",
        claim_count
    )

    return {
        "claims": claims,
        "node_timings": add_timing(
            state,
            "claim_extraction",
            elapsed
        ),
        "current_stage": (
            "claim_extraction"
        ),
        "execution_trace": add_trace(
            state,
            "claim_extraction"
        )
    }

# =========================================================
# Route After Raw Extraction
# =========================================================

def route_after_claim_extraction(
    state: GameHiveGraphState
):

    claims = state[
        "claims"
    ]

    if len(
        claims.claims
    ) == 0:

        # If revisions happened and no factual claim
        # remains, the problematic content may have
        # been removed / fictionalized.
        if (
            state.get(
                "revision_round",
                0
            ) > 0
            and state.get(
                "had_verifiable_claims",
                False
            )
        ):

            return "approved"

        return "no_claims"

    return "scope_router"


# =========================================================
# Claim Scope Router Node
# =========================================================

def claim_scope_router_node(
    state: GameHiveGraphState
):
    print(
        "\n[LangGraph] CLAIM SCOPE ROUTER"
    )

    started = time.perf_counter()

    scoped_claims = route_claim_scopes(
        claims=state[
            "claims"
        ],
        state=state[
            "game_state"
        ]
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        f"[Timing] claim_scope_router: {elapsed:.2f}s"
    )

    cultural_claims = get_cultural_claims(
        scoped_claims
    )

    game_state_claims = (
        get_game_state_claims(
            scoped_claims
        )
    )

    fictional_claims = (
        get_fictional_claims(
            scoped_claims
        )
    )

    print(
        "CULTURAL_FACT:",
        len(cultural_claims)
    )

    print(
        "GAME_STATE_FACT:",
        len(game_state_claims)
    )

    print(
        "FICTIONAL_CONTENT:",
        len(fictional_claims)
    )

    has_verifiable = (
        len(cultural_claims) > 0
        or len(game_state_claims) > 0
    )

    had_verifiable_claims = (
        state.get(
            "had_verifiable_claims",
            False
        )
        or has_verifiable
    )

    return {
        "scoped_claims": scoped_claims,
        "node_timings": add_timing(
            state,
            "claim_scope_router",
            elapsed
        ),
        "had_verifiable_claims": (
            had_verifiable_claims
        ),
        "current_stage": (
            "claim_scope_router"
        ),
        "execution_trace": add_trace(
            state,
            "claim_scope_router"
        )
    }

# =========================================================
# Route After Scope Router
# =========================================================

def route_after_scope_router(
    state: GameHiveGraphState
):
    scoped_claims = state[
        "scoped_claims"
    ]

    game_state_count = len(
        get_game_state_claims(
            scoped_claims
        )
    )

    cultural_count = len(
        get_cultural_claims(
            scoped_claims
        )
    )

    if (
        game_state_count > 0
        or cultural_count > 0
    ):
        return "verification_prep"

    if (
        state.get(
            "revision_round",
            0
        ) > 0
        and state.get(
            "had_verifiable_claims",
            False
        )
    ):
        return "approved"

    return "no_claims"


# =========================================================
# Optimized Verification Preparation
# =========================================================

def verification_prep_node(
    state: GameHiveGraphState
):
    """
    Run independent internal verification and Cultural RAG
    retrieval concurrently when both are needed.
    """

    print(
        "\n[LangGraph] PARALLEL VERIFICATION PREP"
    )

    scoped_claims = state[
        "scoped_claims"
    ]

    game_state_count = len(
        get_game_state_claims(
            scoped_claims
        )
    )

    cultural_count = len(
        get_cultural_claims(
            scoped_claims
        )
    )

    updates: dict[str, Any] = {}

    def run_internal():
        started = time.perf_counter()

        result = verify_game_state_claims(
            scoped_claims=scoped_claims,
            state=state[
                "game_state"
            ]
        )

        return (
            result,
            time.perf_counter()
            - started
        )

    def run_cultural():
        started = time.perf_counter()

        cultural_claims = (
            build_cultural_claim_output(
                scoped_claims
            )
        )

        evidence_packs = (
            build_evidence_packs(
                cultural_claims
            )
        )

        return (
            cultural_claims,
            evidence_packs,
            time.perf_counter()
            - started
        )

    if (
        game_state_count > 0
        and cultural_count > 0
    ):

        print(
            "Running GameState verification and "
            "Cultural RAG in parallel..."
        )

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:

            internal_future = executor.submit(
                run_internal
            )

            cultural_future = executor.submit(
                run_cultural
            )

            (
                internal_results,
                internal_seconds
            ) = internal_future.result()

            (
                cultural_claims,
                evidence_packs,
                cultural_seconds
            ) = cultural_future.result()

        updates[
            "game_state_verification_results"
        ] = internal_results

        updates[
            "cultural_claims"
        ] = cultural_claims

        updates[
            "evidence_packs"
        ] = evidence_packs

        timings = dict(
            state.get(
                "node_timings",
                {}
            )
        )

        timings[
            "game_state_verifier"
        ] = round(
            internal_seconds,
            3
        )

        timings[
            "evidence_retrieval"
        ] = round(
            cultural_seconds,
            3
        )

        updates[
            "node_timings"
        ] = timings

        print(
            f"[Timing] game_state_verifier: "
            f"{internal_seconds:.2f}s"
        )

        print(
            f"[Timing] evidence_retrieval: "
            f"{cultural_seconds:.2f}s"
        )

    elif game_state_count > 0:

        (
            internal_results,
            internal_seconds
        ) = run_internal()

        updates[
            "game_state_verification_results"
        ] = internal_results

        updates[
            "node_timings"
        ] = add_timing(
            state,
            "game_state_verifier",
            internal_seconds
        )

        print(
            f"[Timing] game_state_verifier: "
            f"{internal_seconds:.2f}s"
        )

    elif cultural_count > 0:

        (
            cultural_claims,
            evidence_packs,
            cultural_seconds
        ) = run_cultural()

        updates[
            "cultural_claims"
        ] = cultural_claims

        updates[
            "evidence_packs"
        ] = evidence_packs

        updates[
            "node_timings"
        ] = add_timing(
            state,
            "evidence_retrieval",
            cultural_seconds
        )

        print(
            f"[Timing] evidence_retrieval: "
            f"{cultural_seconds:.2f}s"
        )

    updates[
        "current_stage"
    ] = "verification_prep"

    updates[
        "execution_trace"
    ] = add_trace(
        state,
        "verification_prep"
    )

    return updates


def route_after_verification_prep(
    state: GameHiveGraphState
):
    internal_results = state.get(
        "game_state_verification_results"
    )

    if internal_results is not None:

        has_internal_problem = any(
            item.verdict
            in {
                "UNSUPPORTED",
                "INSUFFICIENT"
            }
            for item
            in internal_results.verifications
        )

        if has_internal_problem:
            return "human_review"

    cultural_count = len(
        get_cultural_claims(
            state[
                "scoped_claims"
            ]
        )
    )

    if cultural_count > 0:
        return "cultural_verifier"

    return "approved"


# =========================================================
# Internal Game-State Verifier Node
# =========================================================

def game_state_verifier_node(
    state: GameHiveGraphState
):

    print(
        "\n[LangGraph] INTERNAL STATE VERIFIER"
    )


    results = verify_game_state_claims(

        scoped_claims=state[
            "scoped_claims"
        ],

        state=state[
            "game_state"
        ]
    )


    supported = sum(

        1

        for item in results.verifications

        if item.verdict == "SUPPORTED"
    )


    unsupported = sum(

        1

        for item in results.verifications

        if item.verdict == "UNSUPPORTED"
    )


    insufficient = sum(

        1

        for item in results.verifications

        if item.verdict == "INSUFFICIENT"
    )


    print(
        "Internal SUPPORTED:",
        supported
    )

    print(
        "Internal UNSUPPORTED:",
        unsupported
    )

    print(
        "Internal INSUFFICIENT:",
        insufficient
    )


    return {
        "game_state_verification_results": (
            results
        ),

        "current_stage": (
            "game_state_verifier"
        ),

        "execution_trace": add_trace(
            state,
            "game_state_verifier"
        )
    }


# =========================================================
# Route After Internal Verification
# =========================================================

def route_after_game_state_verifier(
    state: GameHiveGraphState
):

    results = state[
        "game_state_verification_results"
    ]


    # -----------------------------------------------------
    # Internal inconsistency detected
    # -----------------------------------------------------
    # For now, we fail safely rather than asking
    # Cultural RAG to solve an internal-state problem.
    # -----------------------------------------------------

    has_internal_problem = any(

        item.verdict
        in {
            "UNSUPPORTED",
            "INSUFFICIENT"
        }

        for item in results.verifications
    )


    if has_internal_problem:

        return "human_review"


    # -----------------------------------------------------
    # Internal claims are valid.
    # Check whether cultural claims also exist.
    # -----------------------------------------------------

    cultural_count = len(

        get_cultural_claims(
            state[
                "scoped_claims"
            ]
        )
    )


    if cultural_count > 0:

        return "retrieve_evidence"


    # -----------------------------------------------------
    # Only internal claims existed and all passed.
    # -----------------------------------------------------

    return "approved"


# =========================================================
# Convert Atomic Cultural Claims
# =========================================================

def build_cultural_claim_output(
    scoped_claims: ClaimScopeOutput
) -> ClaimExtractionOutput:
    """
    Convert CULTURAL_FACT atomic claims into the
    existing ClaimExtractionOutput expected by
    GameHive's Evidence Pack builder.
    """

    atomic_cultural_claims = (
        get_cultural_claims(
            scoped_claims
        )
    )


    converted_claims = []


    for item in atomic_cultural_claims:

        converted_claims.append(

            CulturalClaim(

                claim=item.claim,

                claim_type=(
                    item.claim_type
                ),

                requires_verification=True,

                source_area=(
                    item.source_area
                )
            )
        )


    return ClaimExtractionOutput(
        claims=converted_claims
    )


# =========================================================
# Cultural Evidence Retrieval Node
# =========================================================

def evidence_retrieval_node(
    state: GameHiveGraphState
):

    print(
        "\n[LangGraph] CULTURAL RAG"
    )


    cultural_claims = (
        build_cultural_claim_output(
            state[
                "scoped_claims"
            ]
        )
    )


    print(
        "Cultural Claims Sent to RAG:",
        len(
            cultural_claims.claims
        )
    )


    evidence_packs = (
        build_evidence_packs(
            cultural_claims
        )
    )


    print(
        "Evidence Packs:",
        len(
            evidence_packs.claim_packs
        )
    )


    return {
        "cultural_claims": (
            cultural_claims
        ),

        "evidence_packs": (
            evidence_packs
        ),

        "current_stage": (
            "evidence_retrieval"
        ),

        "execution_trace": add_trace(
            state,
            "evidence_retrieval"
        )
    }


# =========================================================
# Cultural Verifier Node
# =========================================================

def cultural_verifier_node(
    state: GameHiveGraphState
):
    print(
        "\n[LangGraph] CULTURAL VERIFIER"
    )

    started = time.perf_counter()

    verification_results = (
        verify_all_claims(
            state[
                "evidence_packs"
            ]
        )
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        f"[Timing] cultural_verifier: {elapsed:.2f}s"
    )

    return {
        "verification_results": (
            verification_results
        ),

        "retry_results": None,

        "node_timings": add_timing(
            state,
            "cultural_verifier",
            elapsed
        ),
        "current_stage": (
            "cultural_verifier"
        ),
        "execution_trace": add_trace(
            state,
            "cultural_verifier"
        )
    }


# =========================================================
# Route After Cultural Verification
# =========================================================

def route_after_cultural_verifier(
    state: GameHiveGraphState
):
    """
    Retry evidence only when the verifier actually returns
    INSUFFICIENT. Other verdicts can go straight to the gate.
    """

    verification_results = state[
        "verification_results"
    ]

    has_insufficient = any(
        item.verdict == "INSUFFICIENT"
        for item
        in verification_results.verifications
    )

    if has_insufficient:
        return "retry_evidence"

    return "revision_gate"


# =========================================================
# Evidence Retry Node
# =========================================================

def evidence_retry_node(
    state: GameHiveGraphState
):
    print(
        "\n[LangGraph] EVIDENCE RETRY"
    )

    started = time.perf_counter()

    retry_results = (
        retry_insufficient_evidence(
            state[
                "evidence_packs"
            ],
            state[
                "verification_results"
            ]
        )
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    updated_verification = (
        retry_results
        .updated_verification_results
    )

    print(
        "Evidence Retries:",
        len(
            retry_results.retry_results
        )
    )

    print(
        f"[Timing] evidence_retry: {elapsed:.2f}s"
    )

    return {
        "retry_results": (
            retry_results
        ),
        "verification_results": (
            updated_verification
        ),
        "node_timings": add_timing(
            state,
            "evidence_retry",
            elapsed
        ),
        "current_stage": (
            "evidence_retry"
        ),
        "execution_trace": add_trace(
            state,
            "evidence_retry"
        )
    }

# =========================================================
# Cultural Revision Gate Node
# =========================================================

def revision_gate_node(
    state: GameHiveGraphState
):
    print(
        "\n[LangGraph] REVISION GATE"
    )

    retry_results = state.get(
        "retry_results"
    )

    retried_claims = (
        retry_results.retried_claims
        if retry_results is not None
        else []
    )

    started = time.perf_counter()

    revision_decisions = (
        run_revision_gate(
            state[
                "verification_results"
            ],
            state[
                "evidence_packs"
            ],
            retried_claims=(
                retried_claims
            )
        )
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    keep_count = sum(
        1
        for decision
        in revision_decisions.decisions
        if decision.action == "KEEP"
    )

    revision_count = sum(
        1
        for decision
        in revision_decisions.decisions
        if decision.requires_revision
    )

    human_count = sum(
        1
        for decision
        in revision_decisions.decisions
        if decision.requires_human_review
    )

    print(
        "KEEP:",
        keep_count
    )

    print(
        "NEEDS REVISION:",
        revision_count
    )

    print(
        "HUMAN REVIEW:",
        human_count
    )

    print(
        f"[Timing] revision_gate: {elapsed:.2f}s"
    )

    return {
        "revision_decisions": (
            revision_decisions
        ),
        "node_timings": add_timing(
            state,
            "revision_gate",
            elapsed
        ),
        "current_stage": (
            "revision_gate"
        ),
        "execution_trace": add_trace(
            state,
            "revision_gate"
        )
    }

# =========================================================
# Route After Cultural Revision Gate
# =========================================================

def route_after_revision_gate(
    state: GameHiveGraphState
):

    gate = state[
        "revision_decisions"
    ]


    decisions = (
        gate.decisions
    )


    # -----------------------------------------------------
    # Defensive Empty Case
    # -----------------------------------------------------

    if len(decisions) == 0:

        if state.get(
            "had_verifiable_claims",
            False
        ):

            return "approved"

        return "no_claims"


    # -----------------------------------------------------
    # Human Review Already Required
    # -----------------------------------------------------

    if any(

        decision.requires_human_review

        for decision in decisions
    ):

        return "human_review"


    # -----------------------------------------------------
    # Defensive Retry Route
    # -----------------------------------------------------

    if any(

        decision.requires_evidence_retry

        for decision in decisions
    ):

        return "retry_evidence"


    # -----------------------------------------------------
    # Revision Required
    # -----------------------------------------------------

    needs_revision = any(

        decision.requires_revision

        for decision in decisions
    )


    if needs_revision:

        current_round = state.get(
            "revision_round",
            0
        )


        max_rounds = state.get(
            "max_revision_rounds",
            DEFAULT_MAX_REVISION_ROUNDS
        )


        if current_round >= max_rounds:

            return "human_review"


        return "revise"


    # -----------------------------------------------------
    # All Claims Passed
    # -----------------------------------------------------

    if all(

        decision.action == "KEEP"

        for decision in decisions
    ):

        return "approved"


    # -----------------------------------------------------
    # Safety Fallback
    # -----------------------------------------------------

    return "human_review"


# =========================================================
# Targeted Revision Node
# =========================================================

def targeted_revision_node(
    state: GameHiveGraphState
):
    next_round = (
        state.get(
            "revision_round",
            0
        )
        + 1
    )

    print(
        "\n================================="
    )

    print(
        f"LANGGRAPH REVISION ROUND "
        f"{next_round}"
    )

    print(
        "================================="
    )

    started = time.perf_counter()

    game_state, revision_report = (
        apply_targeted_revisions(
            state[
                "game_state"
            ],
            state[
                "revision_decisions"
            ],
            state[
                "verification_results"
            ],
            state[
                "evidence_packs"
            ]
        )
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        "Revised Agents:",
        revision_report.revised_agents
    )

    print(
        f"[Timing] targeted_revision: {elapsed:.2f}s"
    )

    return {
        "game_state": (
            game_state
        ),
        "revision_round": (
            next_round
        ),
        "last_revision_report": (
            revision_report
        ),
        "node_timings": add_timing(
            state,
            "targeted_revision",
            elapsed
        ),
        "current_stage": (
            "targeted_revision"
        ),
        "execution_trace": add_trace(
            state,
            f"targeted_revision_round_{next_round}"
        )
    }

# =========================================================
# Escalate Cultural Decisions to Human Review
# =========================================================

def escalate_to_human_review(
    revision_gate: RevisionGateOutput
):

    escalated_decisions = []


    for decision in revision_gate.decisions:

        if decision.action == "KEEP":

            escalated_decisions.append(
                decision
            )

            continue


        if decision.requires_human_review:

            escalated_decisions.append(
                decision
            )

            continue


        if (
            decision.requires_revision
            or decision.requires_evidence_retry
        ):

            updated_decision = (
                decision.model_copy(
                    update={
                        "action": (
                            "HUMAN_REVIEW"
                        ),

                        "target_agent": (
                            "none"
                        ),

                        "requires_revision": (
                            False
                        ),

                        "requires_evidence_retry": (
                            False
                        ),

                        "requires_human_review": (
                            True
                        ),

                        "reason": (
                            decision.reason
                            + " Maximum automatic "
                            + "revision rounds were "
                            + "reached. The claim "
                            + "requires human review."
                        )
                    }
                )
            )


            escalated_decisions.append(
                updated_decision
            )

            continue


        escalated_decisions.append(
            decision
        )


    return RevisionGateOutput(
        decisions=escalated_decisions
    )


# =========================================================
# Approved Node
# =========================================================

def approved_node(
    state: GameHiveGraphState
):

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE FINAL STATUS: APPROVED"
    )

    print(
        "================================="
    )


    return {
        "approved": True,

        "final_status": "APPROVED",

        "requires_human_review": False,

        "current_stage": "approved",

        "execution_trace": add_trace(
            state,
            "approved"
        )
    }


# =========================================================
# Human Review Node
# =========================================================

def human_review_node(
    state: GameHiveGraphState
):

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE FINAL STATUS:"
    )

    print(
        "HUMAN REVIEW REQUIRED"
    )

    print(
        "================================="
    )


    gate = state.get(
        "revision_decisions"
    )


    # Cultural gate exists
    if gate is not None:

        gate = escalate_to_human_review(
            gate
        )


    return {
        "revision_decisions": gate,

        "approved": False,

        "final_status": (
            "HUMAN_REVIEW_REQUIRED"
        ),

        "requires_human_review": True,

        "current_stage": (
            "human_review"
        ),

        "execution_trace": add_trace(
            state,
            "human_review"
        )
    }


# =========================================================
# No Verifiable Claims Node
# =========================================================

def no_claims_node(
    state: GameHiveGraphState
):

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE FINAL STATUS:"
    )

    print(
        "NO VERIFIABLE CLAIMS"
    )

    print(
        "================================="
    )


    return {
        "approved": False,

        "final_status": (
            "NO_VERIFIABLE_CLAIMS"
        ),

        "requires_human_review": False,

        "current_stage": (
            "no_verifiable_claims"
        ),

        "execution_trace": add_trace(
            state,
            "no_verifiable_claims"
        )
    }


# =========================================================
# Build GameHive LangGraph
# =========================================================

def build_gamehive_graph():
    workflow = StateGraph(
        GameHiveGraphState
    )

    workflow.add_node(
        "story_agent",
        story_node
    )

    workflow.add_node(
        "gameplay_agent",
        gameplay_node
    )

    workflow.add_node(
        "level_design_agent",
        level_design_node
    )

    workflow.add_node(
        "claim_extraction",
        claim_extraction_node
    )

    workflow.add_node(
        "claim_scope_router",
        claim_scope_router_node
    )

    workflow.add_node(
        "verification_prep",
        verification_prep_node
    )

    workflow.add_node(
        "cultural_verifier",
        cultural_verifier_node
    )

    workflow.add_node(
        "evidence_retry",
        evidence_retry_node
    )

    workflow.add_node(
        "revision_gate",
        revision_gate_node
    )

    workflow.add_node(
        "targeted_revision",
        targeted_revision_node
    )

    workflow.add_node(
        "approved",
        approved_node
    )

    workflow.add_node(
        "human_review",
        human_review_node
    )

    workflow.add_node(
        "no_claims",
        no_claims_node
    )

    workflow.add_edge(
        START,
        "story_agent"
    )

    workflow.add_edge(
        "story_agent",
        "gameplay_agent"
    )

    workflow.add_edge(
        "gameplay_agent",
        "level_design_agent"
    )

    workflow.add_edge(
        "level_design_agent",
        "claim_extraction"
    )

    workflow.add_conditional_edges(
        "claim_extraction",
        route_after_claim_extraction,
        {
            "scope_router": (
                "claim_scope_router"
            ),
            "approved": (
                "approved"
            ),
            "no_claims": (
                "no_claims"
            )
        }
    )

    workflow.add_conditional_edges(
        "claim_scope_router",
        route_after_scope_router,
        {
            "verification_prep": (
                "verification_prep"
            ),
            "approved": (
                "approved"
            ),
            "no_claims": (
                "no_claims"
            )
        }
    )

    workflow.add_conditional_edges(
        "verification_prep",
        route_after_verification_prep,
        {
            "cultural_verifier": (
                "cultural_verifier"
            ),
            "approved": (
                "approved"
            ),
            "human_review": (
                "human_review"
            )
        }
    )

    workflow.add_conditional_edges(
        "cultural_verifier",
        route_after_cultural_verifier,
        {
            "retry_evidence": (
                "evidence_retry"
            ),
            "revision_gate": (
                "revision_gate"
            )
        }
    )

    workflow.add_edge(
        "evidence_retry",
        "revision_gate"
    )

    workflow.add_conditional_edges(
        "revision_gate",
        route_after_revision_gate,
        {
            "revise": (
                "targeted_revision"
            ),
            "retry_evidence": (
                "evidence_retry"
            ),
            "approved": (
                "approved"
            ),
            "human_review": (
                "human_review"
            ),
            "no_claims": (
                "no_claims"
            )
        }
    )

    workflow.add_edge(
        "targeted_revision",
        "claim_extraction"
    )

    workflow.add_edge(
        "approved",
        END
    )

    workflow.add_edge(
        "human_review",
        END
    )

    workflow.add_edge(
        "no_claims",
        END
    )

    return workflow.compile()

# =========================================================
# Compiled Graph
# =========================================================

gamehive_graph = (
    build_gamehive_graph()
)


# =========================================================
# Convenience Runner
# =========================================================

def run_gamehive_graph(
    game_idea: str,
    max_revision_rounds: int = (
        DEFAULT_MAX_REVISION_ROUNDS
    )
):
    """
    The current Streamlit UI uses:
        FAST = 1
        DEEP VERIFICATION = 2

    To keep the UI unchanged while reducing latency:
        FAST -> 0 automatic revision rounds
        DEEP -> 1 automatic revision round

    The initial verification pass still runs in both modes.
    """

    total_started = time.perf_counter()

    requested_revision_budget = max(
        0,
        int(
            max_revision_rounds
        )
    )

    effective_revision_rounds = max(
        0,
        requested_revision_budget - 1
    )

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE PERFORMANCE MODE"
    )

    print(
        "================================="
    )

    print(
        "Requested UI revision budget:",
        requested_revision_budget
    )

    print(
        "Effective automatic revisions:",
        effective_revision_rounds
    )

    initial_game_state = GameState(
        game_idea=game_idea
    )

    initial_graph_state: GameHiveGraphState = {
        "game_state": (
            initial_game_state
        ),
        "revision_round": 0,
        "max_revision_rounds": (
            effective_revision_rounds
        ),
        "had_verifiable_claims": False,
        "approved": False,
        "final_status": "RUNNING",
        "requires_human_review": False,
        "current_stage": "start",
        "execution_trace": [
            "start"
        ],
        "node_timings": {}
    }

    result = gamehive_graph.invoke(
        initial_graph_state
    )

    total_seconds = (
        time.perf_counter()
        - total_started
    )

    result[
        "total_generation_seconds"
    ] = round(
        total_seconds,
        3
    )

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE TIMING SUMMARY"
    )

    print(
        "================================="
    )

    for stage, seconds in result.get(
        "node_timings",
        {}
    ).items():

        print(
            f"{stage}: {seconds:.2f}s"
        )

    print(
        f"TOTAL: {total_seconds:.2f}s"
    )

    return result
