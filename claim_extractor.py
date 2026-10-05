import os
import json

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict

from state import GameState


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

# Speed profile: extraction is classification/selection, not deep reasoning.
REASONING_EFFORT = "none"
MAX_OUTPUT_TOKENS = 1800


# =========================================================
# Structured Output Models
# =========================================================

class CulturalClaim(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    claim: str

    claim_type: str

    requires_verification: bool

    source_area: str


class ClaimExtractionOutput(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    claims: list[CulturalClaim]


# =========================================================
# Claim Extractor
# =========================================================

def extract_cultural_claims(
    state: GameState
) -> ClaimExtractionOutput:

    """
    Extract only cultural, historical,
    geographical, archaeological, architectural,
    or heritage claims that may require verification.
    """

    # =====================================================
    # Prepare Existing Agent Outputs
    # =====================================================

    story_text = (
        state.story.model_dump_json(
            indent=2
        )
        if state.story
        else "{}"
    )


    gameplay_text = (
        state.gameplay.model_dump_json(
            indent=2
        )
        if state.gameplay
        else "{}"
    )


    levels_text = (
        state.levels.model_dump_json(
            indent=2
        )
        if state.levels
        else "{}"
    )


    schema = (
        ClaimExtractionOutput
        .model_json_schema()
    )


    # =====================================================
    # System Prompt
    # =====================================================

    system_prompt = """
You are the Cultural Claim Extraction Agent
inside GameHive.

Your job is NOT to decide whether a statement
is true or false.

Your job is ONLY to identify factual claims
that should be checked using trusted cultural,
historical, geographical, archaeological,
architectural, or heritage evidence.


=====================================================
WHAT TO EXTRACT
=====================================================

Extract claims involving:

- Saudi cultural practices
- traditions
- heritage
- historical claims
- architecture
- crafts
- clothing
- food
- music
- dance
- oral traditions
- rituals
- archaeology
- historic sites
- regional identity
- cultural geography
- named cultural elements
- historical locations
- caravan routes
- traditional settlements
- cultural landscapes


=====================================================
WHAT NOT TO EXTRACT
=====================================================

Do NOT extract:

- ordinary gameplay mechanics
- scoring systems
- health systems
- inventory mechanics
- progression systems
- purely fictional character motivations
- generic narrative conflicts
- fictional level names that are clearly
  presented as fictional


=====================================================
FICTIONAL CONTENT RULE
=====================================================

Do NOT extract purely fictional content unless
the game presents it as authentic Saudi culture,
history, heritage, geography, archaeology,
architecture, or tradition.

For example:

Do NOT extract:

"The player collects Preservation Points."

This is clearly a gameplay mechanic.

DO extract:

"The fort uses traditional Asiri architectural
features."

This is a factual cultural claim that requires
verification.


=====================================================
COMPOUND CLAIM RULE
=====================================================

When possible, keep factual claims specific.

Avoid combining several unrelated factual claims
into one sentence.

For example, instead of:

"Asir villages contain terraced farms, ancient
forts, caravan roads, and traditional stone paths."

Prefer separate claims when these facts require
different evidence.


=====================================================
SOURCE AREA
=====================================================

source_area must be exactly one of:

story
gameplay
level_design


=====================================================
CLAIM TYPE
=====================================================

claim_type should use a short useful category.

Examples:

traditional_craft
architecture
ritual
food
music
dance
historical_claim
archaeology
regional_culture
intangible_heritage
cultural_geography
historic_site
other


=====================================================
IMPORTANT
=====================================================

Do NOT verify the claims.

Do NOT use outside knowledge.

Do NOT decide whether a claim is supported.

Do NOT invent evidence.

Only identify statements that should later
be checked by the GameHive Cultural Evidence
Verification Pipeline.
"""


    # =====================================================
    # User Prompt
    # =====================================================

    user_prompt = f"""
STORY OUTPUT:

{story_text}


GAMEPLAY OUTPUT:

{gameplay_text}


LEVEL DESIGN OUTPUT:

{levels_text}


TASK:

Extract all meaningful cultural, historical,
geographical, archaeological, architectural,
or heritage claims that require verification.

Avoid ordinary gameplay facts.

Avoid duplicate claims.

Keep each claim as specific as possible.
"""


    # =====================================================
    # OpenAI Structured Response
    # =====================================================

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

                "name":
                    "cultural_claim_extraction",

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
            "Claim Extractor response."
        )


    try:

        data = json.loads(
            raw_output
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            "Claim Extractor returned invalid JSON."
        ) from error


    return ClaimExtractionOutput(
        **data
    )


# =========================================================
# Print Helper
# =========================================================

def print_claims(
    result: ClaimExtractionOutput
):

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE CULTURAL CLAIMS"
    )

    print(
        "================================="
    )


    if not result.claims:

        print(
            "\nNo cultural claims requiring "
            "verification found."
        )

        return


    print(
        f"\nClaims Found: "
        f"{len(result.claims)}"
    )


    for index, claim in enumerate(
        result.claims,
        start=1
    ):

        print(
            f"\nCLAIM {index}"
        )

        print(
            f"Claim: {claim.claim}"
        )

        print(
            f"Type: {claim.claim_type}"
        )

        print(
            f"Source Area: "
            f"{claim.source_area}"
        )

        print(
            f"Requires Verification: "
            f"{claim.requires_verification}"
        )