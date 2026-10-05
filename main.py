from workflow.gamehive_graph import (
    run_gamehive_graph
)

from agents.claim_extractor import (
    print_claims
)

from RAG.evidence_pack import (
    print_evidence_packs
)

from agents.culture_verifier import (
    print_verification_results
)

from agents.revision_gate import (
    print_revision_gate
)


# =========================================================
# Game Idea
# =========================================================

GAME_IDEA = """
An adventure game inspired by Saudi culture where the player
explores different regions and uncovers a forgotten
historical mystery.
"""


# =========================================================
# Run GameHive LangGraph
# =========================================================

print(
    "\n================================="
)

print(
    "GAMEHIVE LANGGRAPH SYSTEM"
)

print(
    "================================="
)


result = run_gamehive_graph(
    game_idea=GAME_IDEA,
    max_revision_rounds=2
)


# =========================================================
# Extract Final State
# =========================================================

game_state = result[
    "game_state"
]


final_status = result.get(
    "final_status",
    "UNKNOWN"
)


approved = result.get(
    "approved",
    False
)


requires_human_review = result.get(
    "requires_human_review",
    False
)


execution_trace = result.get(
    "execution_trace",
    []
)


revision_round = result.get(
    "revision_round",
    0
)


# =========================================================
# Final Game Design
# =========================================================

print(
    "\n\n================================="
)

print(
    "FINAL GAMEHIVE GAME DESIGN"
)

print(
    "================================="
)


# =========================================================
# Story
# =========================================================

print(
    "\n=== STORY ==="
)


print(
    "\nPremise:"
)

print(
    game_state.story.premise
)


print(
    "\nCharacters:"
)

for character in game_state.story.characters:

    print(
        "-",
        character
    )


print(
    "\nCentral Conflict:"
)

print(
    game_state.story.central_conflict
)


# =========================================================
# Gameplay
# =========================================================

print(
    "\n=== GAMEPLAY ==="
)


print(
    "\nCore Gameplay Loop:"
)

print(
    game_state.gameplay.core_gameplay_loop
)


print(
    "\nKey Mechanics:"
)

for mechanic in game_state.gameplay.key_mechanics:

    print(
        "-",
        mechanic
    )


print(
    "\nProgression System:"
)

print(
    game_state.gameplay.progression_system
)


# =========================================================
# Level Design
# =========================================================

print(
    "\n=== LEVEL DESIGN ==="
)


for i in range(
    len(
        game_state.levels.level_names
    )
):

    print(
        f"\nLEVEL {i + 1}"
    )


    print(
        "Name:"
    )

    print(
        game_state.levels.level_names[i]
    )


    print(
        "Setting:"
    )

    print(
        game_state.levels.level_settings[i]
    )


    print(
        "Key Challenge:"
    )

    print(
        game_state.levels.key_challenges[i]
    )


    print(
        "Mechanic Focus:"
    )

    print(
        game_state.levels.mechanic_focus[i]
    )


    print(
        "Progression Purpose:"
    )

    print(
        game_state.levels.progression_purpose[i]
    )


# =========================================================
# Final Cultural Claims
# =========================================================

claims = result.get(
    "claims"
)


if claims is not None:

    print(
        "\n\n=== FINAL CULTURAL CLAIMS ==="
    )

    print_claims(
        claims
    )


# =========================================================
# Final Evidence Packs
# =========================================================

evidence_packs = result.get(
    "evidence_packs"
)


if evidence_packs is not None:

    print(
        "\n=== FINAL EVIDENCE PACKS ==="
    )

    print_evidence_packs(
        evidence_packs
    )


# =========================================================
# Final Cultural Verification
# =========================================================

verification_results = result.get(
    "verification_results"
)


if verification_results is not None:

    print(
        "\n=== FINAL CULTURAL VERIFICATION ==="
    )

    print_verification_results(
        verification_results
    )


# =========================================================
# Final Revision Gate
# =========================================================

revision_decisions = result.get(
    "revision_decisions"
)


if revision_decisions is not None:

    print(
        "\n=== FINAL APPROVAL GATE ==="
    )

    print_revision_gate(
        revision_decisions
    )


# =========================================================
# LangGraph Execution Trace
# =========================================================

print(
    "\n\n================================="
)

print(
    "LANGGRAPH EXECUTION TRACE"
)

print(
    "================================="
)


for index, stage in enumerate(
    execution_trace,
    start=1
):

    print(
        f"{index}. {stage}"
    )


# =========================================================
# Final Workflow Summary
# =========================================================

print(
    "\n================================="
)

print(
    "GAMEHIVE WORKFLOW SUMMARY"
)

print(
    "================================="
)


print(
    "Revision Rounds:",
    revision_round
)


print(
    "Approved:",
    approved
)


print(
    "Human Review:",
    requires_human_review
)


print(
    "Final Status:",
    final_status
)


# =========================================================
# Friendly Final Result
# =========================================================

if final_status == "APPROVED":

    print(
        "\n✅ GAMEHIVE RESULT: APPROVED"
    )

    print(
        "All remaining verifiable cultural "
        "claims passed the final evidence gate."
    )


elif final_status == "HUMAN_REVIEW_REQUIRED":

    print(
        "\n⚠ GAMEHIVE RESULT: HUMAN REVIEW REQUIRED"
    )

    print(
        "The automatic correction limit was reached "
        "or conflicting evidence requires a person "
        "to review the remaining claims."
    )


elif final_status == "NO_VERIFIABLE_CLAIMS":

    print(
        "\nℹ GAMEHIVE RESULT: "
        "NO VERIFIABLE CULTURAL CLAIMS"
    )

    print(
        "No cultural factual claims requiring "
        "external verification were detected."
    )


else:

    print(
        "\n⚠ GAMEHIVE RESULT:",
        final_status
    )