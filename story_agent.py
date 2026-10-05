import os
import json

from dotenv import load_dotenv
from openai import OpenAI

from state import (
    GameState,
    StoryOutput
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
# Story Agent
# =========================================================

def story_agent(
    state: GameState
) -> GameState:

    schema = (
        StoryOutput
        .model_json_schema()
    )


    # =====================================================
    # System Prompt
    # =====================================================

    system_prompt = """
You are the Story Agent inside GameHive,
a multi-agent AI game design system.

ROLE:
You are responsible ONLY for narrative design.

STRICT BOUNDARIES:

Do NOT design:
- gameplay mechanics
- puzzles
- player controls
- progression systems
- level layouts
- scoring systems
- win/lose conditions
- art direction
- audio direction

CULTURAL SAFETY:

You may create fictional narrative elements inspired
by the user's brief, but never present invented folklore,
traditions, historical claims, heritage facts,
or cultural practices as authentic facts.

If cultural or historical information requires verification,
leave it for the Culture Agent.

Do not stereotype Saudi regions, communities,
occupations, traditions, or cultural identities.

YOUR RESPONSIBILITY:

- Core story premise
- Main characters
- Character motivations
- Central narrative conflict
- Fictional world context
- Narrative tone

AGENT HANDOFF RULE:

Do not perform tasks belonging to Gameplay Agent,
Level Design Agent, Culture Agent, Art Agent,
Audio Agent, or any other specialist agent.

Return only information required by StoryOutput.
"""


    # =====================================================
    # User Prompt
    # =====================================================

    user_prompt = f"""
GAME IDEA:

{state.game_idea}


TASK:

Create the narrative foundation for this game.

Stay strictly within the Story Agent role.

Do not design gameplay mechanics or level layouts.

Do not present invented Saudi cultural or historical
information as verified fact.
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

                "name": "story_output",

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
            "OpenAI returned an empty Story Agent response."
        )


    try:

        data = json.loads(
            raw_output
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            "Story Agent returned invalid JSON."
        ) from error


    # =====================================================
    # Update Shared State
    # =====================================================

    state.story = StoryOutput(
        **data
    )


    return state