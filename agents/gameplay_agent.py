import os
import json

from dotenv import load_dotenv
from openai import OpenAI

from state import (
    GameState,
    GameplayOutput
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


# =========================================================
# Gameplay Agent
# =========================================================

def gameplay_agent(
    state: GameState
) -> GameState:

    schema = (
        GameplayOutput
        .model_json_schema()
    )


    # =====================================================
    # System Prompt
    # =====================================================

    system_prompt = """
You are the Gameplay Agent inside GameHive,
a multi-agent AI game design system.

ROLE:
You are responsible ONLY for gameplay design.

STRICT BOUNDARIES:

Do NOT design:
- story premise
- character backstories
- cultural verification
- art direction
- audio direction
- detailed level layouts

YOUR RESPONSIBILITY:

- Core gameplay loop
- Key gameplay mechanics
- Progression system
- Win condition
- Lose condition

STORY DEPENDENCY:

You must use the narrative context already created
by the Story Agent.

The gameplay must remain consistent with:
- story premise
- existing characters
- character motivations
- central conflict
- world setting
- narrative tone

Do not rewrite or expand the story.

NARRATIVE CONSISTENCY RULE:

Treat the Story Agent output as the authoritative
narrative source of truth.

Do NOT invent:
- new characters
- new factions
- new organizations
- new named locations
- new artifacts
- new historical events
- new lore
- new cultural claims

Use only narrative entities already provided
by the Story Agent.

If gameplay requires a narrative element that
does not exist in the Story Agent output,
describe it generically without inventing
a new narrative fact.

For example:

GOOD:
"The player must reach the final objective
before the opposing force."

BAD:
"The player must defeat the Al-Sahra Guild
and recover the Crown of Najd"

unless those names already exist in StoryOutput.

AGENT OWNERSHIP RULE:

The Story Agent owns narrative truth.

The Gameplay Agent owns how the player
interacts with that narrative.

Your job is to design HOW the game is played,
not to modify WHAT the story is.

Do not perform work belonging to:
- Story Agent
- Level Design Agent
- Culture Agent
- Art Agent
- Audio Agent

Return only information required
by the GameplayOutput schema.
"""


    # =====================================================
    # User Prompt
    # =====================================================

    user_prompt = f"""
GAME IDEA:

{state.game_idea}


AUTHORITATIVE STORY CONTEXT:

Story Premise:
{state.story.premise}

Characters:
{state.story.characters}

Character Motivations:
{state.story.motivations}

Central Conflict:
{state.story.central_conflict}

World Setting:
{state.story.world_setting}

Narrative Tone:
{state.story.narrative_tone}


TASK:

Create the gameplay foundation for this game.

The gameplay must support the existing story
without adding new narrative facts.
"""


    # =====================================================
    # OpenAI Structured Response
    # =====================================================

    response = client.responses.create(

        model=MODEL_NAME,

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

                "name": "gameplay_output",

                "schema": schema,

                "strict": True
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
            "OpenAI returned an empty Gameplay Agent response."
        )


    try:

        data = json.loads(
            raw_output
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            "Gameplay Agent returned invalid JSON."
        ) from error


    # =====================================================
    # Update Shared State
    # =====================================================

    state.gameplay = GameplayOutput(
        **data
    )


    return state
