import os
import json

from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict

from state import GameState

from agents.claim_extractor import (
    ClaimExtractionOutput
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

# Speed profile: routing is structured classification.
REASONING_EFFORT = "none"
MAX_OUTPUT_TOKENS = 2400


# =========================================================
# Atomic Claim Model
# =========================================================

class AtomicScopedClaim(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    # Original claim before decomposition
    original_claim: str

    # Atomic claim after decomposition
    claim: str

    scope: Literal[
        "CULTURAL_FACT",
        "GAME_STATE_FACT",
        "FICTIONAL_CONTENT"
    ]

    claim_type: str

    source_area: Literal[
        "story",
        "gameplay",
        "level_design"
    ]

    requires_external_verification: bool

    rationale: str


# =========================================================
# Router Output
# =========================================================

class ClaimScopeOutput(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    atomic_claims: list[
        AtomicScopedClaim
    ]


# =========================================================
# Build Compact Game State
# =========================================================

def build_game_state_context(
    state: GameState
) -> str:
    """
    Provide enough GameHive internal state for the router
    to distinguish game-design facts from external facts.
    """

    story_data = {}

    gameplay_data = {}

    level_data = {}


    if state.story is not None:

        story_data = (
            state.story.model_dump()
        )


    if state.gameplay is not None:

        gameplay_data = (
            state.gameplay.model_dump()
        )


    if state.levels is not None:

        level_data = (
            state.levels.model_dump()
        )


    context = {
        "story": story_data,
        "gameplay": gameplay_data,
        "level_design": level_data
    }


    return json.dumps(
        context,
        ensure_ascii=False,
        indent=2
    )


# =========================================================
# Claim Scope Router
# =========================================================

def route_claim_scopes(
    claims: ClaimExtractionOutput,
    state: GameState
) -> ClaimScopeOutput:
    """
    Classify and decompose extracted claims before RAG.

    Important:
    Mixed claims must be split into atomic claims.

    Example:

    "Al-Ahsa is used as a Saudi oasis setting."

    becomes:

    1. "Al-Ahsa is an oasis."
       → CULTURAL_FACT

    2. "The game uses Al-Ahsa as a setting."
       → GAME_STATE_FACT
    """

    # -----------------------------------------------------
    # Nothing to Route
    # -----------------------------------------------------

    if len(
        claims.claims
    ) == 0:

        return ClaimScopeOutput(
            atomic_claims=[]
        )


    # -----------------------------------------------------
    # Input Claims
    # -----------------------------------------------------

    claims_data = [

        {
            "claim": item.claim,
            "claim_type": item.claim_type,
            "source_area": item.source_area
        }

        for item in claims.claims
    ]


    claims_json = json.dumps(
        claims_data,
        ensure_ascii=False,
        indent=2
    )


    game_state_context = (
        build_game_state_context(
            state
        )
    )


    # -----------------------------------------------------
    # JSON Schema
    # -----------------------------------------------------

    schema = (
        ClaimScopeOutput
        .model_json_schema()
    )


    # -----------------------------------------------------
    # System Prompt
    # -----------------------------------------------------

    system_prompt = """
You are the Claim Scope Router inside GameHive.

Your task is to classify extracted claims BEFORE they are
sent to external cultural evidence retrieval.

This is a critical routing step.

You must determine what kind of evidence can actually
verify each claim.


=========================================================
SCOPE 1: CULTURAL_FACT
=========================================================

Use CULTURAL_FACT when the claim describes an external,
real-world fact that should be verified using trusted
cultural, historical, geographic, archaeological,
architectural, or heritage sources.

Examples:

"Al-Ahsa is an oasis."

"Historic Jeddah is associated with the Red Sea."

"Hima is located in a mountainous area of Saudi Arabia."

"Al-Faw contains archaeological remains."


These claims MAY go to RAG.

Set:

requires_external_verification = true


=========================================================
SCOPE 2: GAME_STATE_FACT
=========================================================

Use GAME_STATE_FACT when the claim describes something
that is true or false because of the generated game design.

Examples:

"The game uses Al-Ahsa as a level setting."

"Level 2 takes place in a coastal community."

"The story includes an archaeological site."

"The gameplay requires regional exploration."


External cultural sources CANNOT verify these claims.

They must be checked against GameHive's own GameState.

Set:

requires_external_verification = false


=========================================================
SCOPE 3: FICTIONAL_CONTENT
=========================================================

Use FICTIONAL_CONTENT when the content is clearly fictional
and is not presented as authentic Saudi history or culture.

Examples:

"The Ninth Map was hidden by the Custodian."

"Noura's grandmother possessed a secret manuscript."

"A fictional archive connects the game's mystery."


These claims should NOT be sent to cultural RAG.

Set:

requires_external_verification = false


=========================================================
CRITICAL RULE: SPLIT MIXED CLAIMS
=========================================================

Never preserve a mixed claim when it contains both:

1. an external real-world fact

and

2. a GameHive internal design fact.


Example:

"Al-Ahsa is used as a Saudi oasis setting."


DO NOT return this as one claim.


Split it into atomic claims:

Claim A:
"Al-Ahsa is an oasis."
Scope:
CULTURAL_FACT


Claim B:
"The game uses Al-Ahsa as a setting."
Scope:
GAME_STATE_FACT


=========================================================
MORE SPLITTING EXAMPLES
=========================================================

Input:

"The Saudi setting draws on documented desert and
mountain environments."


Possible atomic claims:

"Saudi Arabia contains desert environments."
→ CULTURAL_FACT

"Saudi Arabia contains mountainous environments."
→ CULTURAL_FACT

"The game uses desert environments."
→ GAME_STATE_FACT

"The game uses mountainous environments."
→ GAME_STATE_FACT


=========================================================
IMPORTANT RULES
=========================================================

Every returned claim must be ATOMIC.

An atomic claim should contain one independently
verifiable proposition whenever possible.


Do not ask an external source to prove:

- what the game contains
- what an agent generated
- what a level uses
- what the story includes
- what a fictional character does


Do not classify fictional narrative content as a
real cultural fact simply because the game is inspired
by Saudi culture.


Do not invent new facts.

Do not add cultural details that were not present in
the original claim or the GameState.


=========================================================
SOURCE AREA
=========================================================

Preserve the source_area of the original claim:

story
gameplay
level_design


=========================================================
RATIONALE
=========================================================

Provide a short explanation of why the atomic claim
belongs to that scope.


Return only the structured result required by the
provided JSON schema.
"""


    # -----------------------------------------------------
    # User Prompt
    # -----------------------------------------------------

    user_prompt = f"""
EXTRACTED CLAIMS:

{claims_json}


CURRENT GAMEHIVE GAME STATE:

{game_state_context}


TASK:

1. Examine every extracted claim.

2. Split mixed or compound claims into atomic claims.

3. Classify every atomic claim as:

   CULTURAL_FACT
   GAME_STATE_FACT
   FICTIONAL_CONTENT

4. Set requires_external_verification=true ONLY for
   CULTURAL_FACT.

5. Do not invent additional cultural facts.

Return the complete structured result.
"""


    # -----------------------------------------------------
    # OpenAI Call
    # -----------------------------------------------------

    response = client.responses.create(

        model=MODEL_NAME,

        reasoning={
            "effort": REASONING_EFFORT
        },

        max_output_tokens=MAX_OUTPUT_TOKENS,

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
                    "gamehive_claim_scope_router"
                ),

                "schema": schema,

                "strict": True
            }
        },

        store=False
    )


    # -----------------------------------------------------
    # Parse Response
    # -----------------------------------------------------

    raw_output = (
        response.output_text
    )


    if not raw_output:

        raise RuntimeError(
            "Claim Scope Router returned "
            "an empty response."
        )


    try:

        data = json.loads(
            raw_output
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            "Claim Scope Router returned invalid JSON."
        ) from error


    result = ClaimScopeOutput(
        **data
    )


    # =====================================================
    # Safety Normalization
    # =====================================================
    # Do not trust the model to choose this boolean.
    # Derive it deterministically from scope.
    # =====================================================

    normalized_claims = []


    for item in result.atomic_claims:

        requires_external = (
            item.scope
            == "CULTURAL_FACT"
        )


        normalized_item = (
            item.model_copy(
                update={
                    "requires_external_verification": (
                        requires_external
                    )
                }
            )
        )


        normalized_claims.append(
            normalized_item
        )


    return ClaimScopeOutput(
        atomic_claims=normalized_claims
    )


# =========================================================
# Get Cultural Claims Only
# =========================================================

def get_cultural_claims(
    scoped_claims: ClaimScopeOutput
) -> list[AtomicScopedClaim]:
    """
    Claims eligible for external Cultural RAG.
    """

    return [

        item

        for item in scoped_claims.atomic_claims

        if (
            item.scope == "CULTURAL_FACT"
            and item.requires_external_verification
        )
    ]


# =========================================================
# Get Game-State Claims Only
# =========================================================

def get_game_state_claims(
    scoped_claims: ClaimScopeOutput
) -> list[AtomicScopedClaim]:
    """
    Claims that must later be checked against
    GameHive's own structured state.
    """

    return [

        item

        for item in scoped_claims.atomic_claims

        if item.scope == "GAME_STATE_FACT"
    ]


# =========================================================
# Get Fictional Content Only
# =========================================================

def get_fictional_claims(
    scoped_claims: ClaimScopeOutput
) -> list[AtomicScopedClaim]:

    return [

        item

        for item in scoped_claims.atomic_claims

        if item.scope == "FICTIONAL_CONTENT"
    ]


# =========================================================
# Print Router Results
# =========================================================

def print_claim_scope_results(
    scoped_claims: ClaimScopeOutput
):

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE CLAIM SCOPE ROUTER"
    )

    print(
        "================================="
    )


    cultural_count = 0

    game_state_count = 0

    fictional_count = 0


    if len(
        scoped_claims.atomic_claims
    ) == 0:

        print(
            "\nNo claims available for routing."
        )

        return


    for index, item in enumerate(
        scoped_claims.atomic_claims,
        start=1
    ):

        print(
            f"\nATOMIC CLAIM {index}"
        )


        print(
            "Original Claim:"
        )

        print(
            item.original_claim
        )


        print(
            "\nAtomic Claim:"
        )

        print(
            item.claim
        )


        print(
            "\nScope:",
            item.scope
        )


        print(
            "Type:",
            item.claim_type
        )


        print(
            "Source Area:",
            item.source_area
        )


        print(
            "External Verification:",
            item.requires_external_verification
        )


        print(
            "Rationale:",
            item.rationale
        )


        print(
            "-" * 60
        )


        if item.scope == "CULTURAL_FACT":

            cultural_count += 1


        elif item.scope == "GAME_STATE_FACT":

            game_state_count += 1


        elif item.scope == "FICTIONAL_CONTENT":

            fictional_count += 1


    # =====================================================
    # Summary
    # =====================================================

    print(
        "\n================================="
    )

    print(
        "CLAIM SCOPE SUMMARY"
    )

    print(
        "================================="
    )


    print(
        "CULTURAL_FACT:",
        cultural_count
    )


    print(
        "GAME_STATE_FACT:",
        game_state_count
    )


    print(
        "FICTIONAL_CONTENT:",
        fictional_count
    )


    print(
        "TOTAL ATOMIC CLAIMS:",
        len(
            scoped_claims.atomic_claims
        )
    )