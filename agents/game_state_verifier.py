import os
import json

from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict

from state import GameState

from agents.claim_scope_router import (
    ClaimScopeOutput,
    AtomicScopedClaim,
    get_game_state_claims
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

# Internal state matching is a bounded structured task.
REASONING_EFFORT = "none"
MAX_OUTPUT_TOKENS_PER_CLAIM = 650
MAX_BATCH_OUTPUT_TOKENS = 3200


# =========================================================
# Individual Game-State Verification
# =========================================================

class GameStateClaimVerification(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    claim: str

    source_area: Literal[
        "story",
        "gameplay",
        "level_design"
    ]

    verdict: Literal[
        "SUPPORTED",
        "UNSUPPORTED",
        "INSUFFICIENT"
    ]

    reason: str

    matched_state_evidence: list[str]


# =========================================================
# Verification Output
# =========================================================

class GameStateVerificationOutput(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    verifications: list[
        GameStateClaimVerification
    ]


# =========================================================
# Serialize Game State
# =========================================================

def build_internal_state_context(
    state: GameState
) -> str:
    """
    Convert GameHive's structured internal state
    into a compact verification context.
    """

    context = {
        "game_idea": state.game_idea,

        "story": (
            state.story.model_dump()
            if state.story is not None
            else None
        ),

        "gameplay": (
            state.gameplay.model_dump()
            if state.gameplay is not None
            else None
        ),

        "level_design": (
            state.levels.model_dump()
            if state.levels is not None
            else None
        )
    }


    return json.dumps(
        context,
        ensure_ascii=False,
        indent=2
    )


# =========================================================
# Verify One Game-State Claim
# =========================================================

def verify_single_game_state_claim(
    claim: AtomicScopedClaim,
    state: GameState
) -> GameStateClaimVerification:
    """
    Verify an internal GameHive claim ONLY against
    the current structured GameState.

    External cultural knowledge must not be used.
    """

    state_context = (
        build_internal_state_context(
            state
        )
    )


    schema = (
        GameStateClaimVerification
        .model_json_schema()
    )


    # =====================================================
    # System Prompt
    # =====================================================

    system_prompt = """
You are the Internal Game State Verifier inside GameHive.

Your job is to verify claims about the GENERATED GAME
using ONLY the provided GameHive structured state.

You are NOT a cultural verifier.

You are NOT allowed to use outside knowledge.

You are NOT allowed to infer real-world historical,
cultural, archaeological, or geographic facts.


=========================================================
WHAT YOU VERIFY
=========================================================

You verify internal design claims such as:

"The game uses Al-Ahsa as a setting."

"Level 2 takes place in a coastal community."

"The story includes an archaeological site."

"The gameplay includes regional exploration."

"The story contains a fictional map."


=========================================================
SUPPORTED
=========================================================

Use SUPPORTED when the claim is clearly present in the
GameState, even if wording differs slightly.

Example:

Claim:
"The game includes regional exploration."

GameState:
"Regional exploration: navigate varied settings..."

Verdict:
SUPPORTED


=========================================================
UNSUPPORTED
=========================================================

Use UNSUPPORTED when the GameState clearly contradicts
the claim or shows something different.

Example:

Claim:
"Level 2 takes place in Al-Ahsa."

GameState:
Level 2 explicitly takes place in another location.

Verdict:
UNSUPPORTED


=========================================================
INSUFFICIENT
=========================================================

Use INSUFFICIENT when the GameState does not contain enough
information to establish or reject the claim.

Do NOT guess.

Do NOT convert absence into contradiction automatically.


=========================================================
CRITICAL RULE
=========================================================

External facts are irrelevant here.

For example:

Claim:
"The game uses Al-Ahsa as an oasis setting."

You may verify:

"The game uses Al-Ahsa as a setting."

from GameState.

But you may NOT independently decide:

"Al-Ahsa is an oasis."

That belongs to the Cultural RAG verifier.


=========================================================
MATCHED STATE EVIDENCE
=========================================================

matched_state_evidence must contain short excerpts or
precise descriptions of the relevant GameState fields.

Only include evidence actually present in GameState.


=========================================================
SOURCE AREA
=========================================================

Preserve the supplied source_area exactly.


Return only the structured result required by the
provided JSON schema.
"""


    # =====================================================
    # User Prompt
    # =====================================================

    user_prompt = f"""
GAME-STATE CLAIM:

{claim.claim}


SOURCE AREA:

{claim.source_area}


CURRENT GAMEHIVE STATE:

{state_context}


TASK:

Determine whether the game-state claim is:

SUPPORTED
UNSUPPORTED
INSUFFICIENT

Use ONLY the supplied GameHive state.

Do not use external knowledge.
"""


    # =====================================================
    # OpenAI Call
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

                "name": (
                    "gamehive_game_state_verification"
                ),

                "schema": schema,

                "strict": True
            }
        },

        store=False
    )


    raw_output = (
        response.output_text
    )


    if not raw_output:

        raise RuntimeError(
            "Game State Verifier returned "
            "an empty response."
        )


    try:

        data = json.loads(
            raw_output
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            "Game State Verifier returned invalid JSON."
        ) from error


    result = GameStateClaimVerification(
        **data
    )


    # =====================================================
    # Safety Normalization
    # =====================================================
    # Never allow the model to alter the original claim
    # or routing source area.
    # =====================================================

    result = result.model_copy(
        update={
            "claim": claim.claim,
            "source_area": claim.source_area
        }
    )


    return result


# =========================================================
# Verify All Game-State Claims
# =========================================================

def verify_game_state_claims(
    scoped_claims: ClaimScopeOutput,
    state: GameState
) -> GameStateVerificationOutput:
    """
    Verify all GAME_STATE_FACT claims in ONE structured
    OpenAI request.

    CULTURAL_FACT claims remain handled by Cultural RAG.
    FICTIONAL_CONTENT still requires no factual verification.

    If the batch response is malformed, GameHive safely
    falls back to the original per-claim verifier.
    """

    game_state_claims = (
        get_game_state_claims(
            scoped_claims
        )
    )


    if len(game_state_claims) == 0:

        return GameStateVerificationOutput(
            verifications=[]
        )


    total_claims = len(
        game_state_claims
    )


    print(
        "\n================================="
    )

    print(
        "GAMEHIVE INTERNAL STATE VERIFIER"
    )

    print(
        "================================="
    )


    print(
        "Game-State Claims:",
        total_claims
    )


    state_context = (
        build_internal_state_context(
            state
        )
    )


    claims_data = [

        {
            "index": index,
            "claim": claim.claim,
            "source_area": claim.source_area
        }

        for index, claim in enumerate(
            game_state_claims,
            start=1
        )
    ]


    claims_json = json.dumps(
        claims_data,
        ensure_ascii=False,
        indent=2
    )


    schema = (
        GameStateVerificationOutput
        .model_json_schema()
    )


    system_prompt = """
You are the Internal Game State Verifier
inside GameHive.

You will receive MULTIPLE claims about the generated
game plus ONE structured GameHive state.

Verify every claim using ONLY that supplied GameState.

Do NOT use outside knowledge.

For each claim use exactly one verdict:

SUPPORTED
UNSUPPORTED
INSUFFICIENT

SUPPORTED:
The claim is clearly present in GameState,
even if wording differs slightly.

UNSUPPORTED:
GameState clearly contradicts the claim or
explicitly shows something different.

INSUFFICIENT:
GameState does not contain enough information
to establish or reject the claim.

Do not convert absence into contradiction.

Preserve each claim and source_area exactly.
Return one result for every input claim,
in exactly the same order.

matched_state_evidence should contain only short
excerpts or precise descriptions actually present
in the supplied GameState.
"""


    user_prompt = f"""
GAME-STATE CLAIMS:

{claims_json}


CURRENT GAMEHIVE STATE:

{state_context}


TASK:

Verify all {total_claims} claims using ONLY the
supplied GameHive state.

Return exactly {total_claims} verification objects
in the same order.
"""


    try:

        print(
            "\nBatch verifying all internal claims "
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
                        1000,
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

                    "name": (
                        "gamehive_game_state_verification_batch"
                    ),

                    "schema": schema,

                    "strict": True
                }
            },

            store=False
        )


        raw_output = response.output_text


        if not raw_output:

            raise RuntimeError(
                "Game State Verifier returned "
                "an empty batch response."
            )


        data = json.loads(
            raw_output
        )


        result = GameStateVerificationOutput(
            **data
        )


        if len(
            result.verifications
        ) != total_claims:

            raise RuntimeError(
                "Game-state verifier batch count mismatch."
            )


        normalized = []


        for claim, verification in zip(
            game_state_claims,
            result.verifications
        ):

            normalized.append(
                verification.model_copy(
                    update={
                        "claim": claim.claim,
                        "source_area": claim.source_area
                    }
                )
            )


        output = GameStateVerificationOutput(
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
            "\nBatch internal verification fallback activated."
        )

        print(
            "Reason:",
            str(batch_error)[:300]
        )

        print(
            "Falling back to single-claim verification."
        )


        verifications = []


        for index, claim in enumerate(
            game_state_claims,
            start=1
        ):

            print(
                f"\nVerifying internal claim "
                f"{index}/{total_claims}..."
            )


            result = verify_single_game_state_claim(
                claim=claim,
                state=state
            )


            print(
                "Verdict:",
                result.verdict
            )


            verifications.append(
                result
            )


        return GameStateVerificationOutput(
            verifications=verifications
        )


# =========================================================
# Print Results
# =========================================================

def print_game_state_verification(
    output: GameStateVerificationOutput
):

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE INTERNAL STATE VERIFICATION"
    )

    print(
        "================================="
    )


    if len(
        output.verifications
    ) == 0:

        print(
            "\nNo GAME_STATE_FACT claims "
            "required internal verification."
        )

        return


    supported = 0

    unsupported = 0

    insufficient = 0


    for index, item in enumerate(
        output.verifications,
        start=1
    ):

        print(
            f"\nCLAIM {index}"
        )


        print(
            "Claim:",
            item.claim
        )


        print(
            "Source Area:",
            item.source_area
        )


        print(
            "Verdict:",
            item.verdict
        )


        print(
            "Reason:",
            item.reason
        )


        print(
            "\nMatched Game-State Evidence:"
        )


        if item.matched_state_evidence:

            for evidence in (
                item.matched_state_evidence
            ):

                print(
                    "-",
                    evidence
                )

        else:

            print(
                "- None"
            )


        print(
            "-" * 60
        )


        if item.verdict == "SUPPORTED":

            supported += 1


        elif item.verdict == "UNSUPPORTED":

            unsupported += 1


        elif item.verdict == "INSUFFICIENT":

            insufficient += 1


    # =====================================================
    # Summary
    # =====================================================

    print(
        "\n================================="
    )

    print(
        "INTERNAL VERIFICATION SUMMARY"
    )

    print(
        "================================="
    )


    print(
        "SUPPORTED:",
        supported
    )


    print(
        "UNSUPPORTED:",
        unsupported
    )


    print(
        "INSUFFICIENT:",
        insufficient
    )


    print(
        "TOTAL:",
        len(
            output.verifications
        )
    )
