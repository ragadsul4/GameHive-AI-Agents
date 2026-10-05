import os
import json

from dotenv import load_dotenv
from openai import OpenAI

from state import (
    GameState,
    LevelDesignOutput
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
# Level Design Agent
# =========================================================

def level_design_agent(
    state: GameState
) -> GameState:

    schema = (
        LevelDesignOutput
        .model_json_schema()
    )


    # =====================================================
    # System Prompt
    # =====================================================

    system_prompt = """
You are the Level Design Agent inside GameHive,
a multi-agent AI game design system.

ROLE:

You are responsible ONLY for level design.

You receive authoritative information from:

- Story Agent
- Gameplay Agent


STRICT BOUNDARIES:

Do NOT:

- rewrite the story
- invent new characters
- invent new factions
- invent new organizations
- invent new artifacts
- invent new historical events
- create new cultural claims
- redesign gameplay mechanics
- provide art direction
- provide audio direction


STORY CONSISTENCY RULE:

The Story Agent output is the authoritative
narrative source of truth.

Use only narrative entities already present
in StoryOutput.

Do NOT introduce named people, places,
organizations, historical events, or artifacts
that are not already established by the Story Agent.

If a level requires something that has not been
established in StoryOutput, describe it generically
instead of inventing a new narrative fact.


GAMEPLAY CONSISTENCY RULE:

The Gameplay Agent owns gameplay mechanics.

Do not create completely new mechanics.

Design levels that:

- use existing mechanics
- introduce existing mechanics gradually
- combine existing mechanics
- increase challenge
- support progression


CULTURAL SAFETY RULE:

Do not invent cultural, historical, archaeological,
architectural, geographic, or heritage facts and
present them as authentic.

If the existing story or gameplay contains a
cultural element that requires verification,
use it carefully without adding new factual details.

Cultural verification belongs to the
Culture Verification pipeline.


YOUR RESPONSIBILITY:

For each level define:

- level name
- setting
- key challenge
- mechanic focus
- progression purpose


LEVEL DESIGN PRINCIPLES:

The first level should introduce existing
mechanics clearly.

The second level should combine and deepen
existing mechanics.

The final level should create greater complexity
using the same approved gameplay foundation.

Each level must support:

- existing story
- existing characters
- central conflict
- gameplay loop
- existing mechanics
- progression system
- narrative tone


AGENT OWNERSHIP RULE:

Story Agent owns narrative truth.

Gameplay Agent owns gameplay mechanics.

Level Design Agent owns the arrangement,
escalation, and pacing of levels.

Culture verification is handled elsewhere.

Do not perform tasks belonging to:

- Story Agent
- Gameplay Agent
- Culture Agent
- Art Agent
- Audio Agent


Return only information required
by the LevelDesignOutput schema.
"""


    # =====================================================
    # User Prompt
    # =====================================================

    user_prompt = f"""
GAME IDEA:

{state.game_idea}


AUTHORITATIVE STORY:

Premise:
{state.story.premise}

Characters:
{state.story.characters}

Central Conflict:
{state.story.central_conflict}

World Setting:
{state.story.world_setting}

Narrative Tone:
{state.story.narrative_tone}


AUTHORITATIVE GAMEPLAY:

Core Gameplay Loop:
{state.gameplay.core_gameplay_loop}

Key Mechanics:
{state.gameplay.key_mechanics}

Progression System:
{state.gameplay.progression_system}

Win Condition:
{state.gameplay.win_condition}

Lose Condition:
{state.gameplay.lose_condition}


TASK:

Design exactly 3 levels.

Use ONLY the existing story and gameplay foundation.

Do not invent new lore.

Do not invent new historical facts.

Do not invent new cultural facts.

Do not invent completely new mechanics.

Level names may be fictional creative titles,
but they must not be presented as real historical
or cultural locations.

Design the levels by arranging, teaching,
combining, and escalating the existing mechanics.
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

                "name": "level_design_output",

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
            "OpenAI returned an empty Level Design Agent response."
        )


    try:

        data = json.loads(
            raw_output
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            "Level Design Agent returned invalid JSON."
        ) from error


    # =====================================================
    # Update Shared State
    # =====================================================

    state.levels = LevelDesignOutput(
        **data
    )


    return state