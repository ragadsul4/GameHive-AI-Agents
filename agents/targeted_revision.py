import os
import json

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict

from state import (
    GameState,
    StoryOutput,
    GameplayOutput,
    LevelDesignOutput
)

from agents.revision_gate import (
    RevisionGateOutput
)

from agents.culture_verifier import (
    CultureVerificationOutput
)

from RAG.evidence_pack import (
    EvidencePackOutput
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
# Revision Report
# =========================================================

class TargetedRevisionReport(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    revised_agents: list[str]

    targeted_claims: list[str]

    revision_count: int


# =========================================================
# Build Revision Context
# =========================================================

def build_revision_context(
    target_agent: str,
    revision_decisions: RevisionGateOutput,
    verification_results: CultureVerificationOutput,
    evidence_packs: EvidencePackOutput
) -> str:

    """
    Build a focused revision instruction
    for one specific agent.

    Only claims routed to this agent are included.
    """

    verification_by_claim = {
        item.claim: item
        for item in verification_results.verifications
    }


    evidence_by_claim = {
        pack.claim: pack
        for pack in evidence_packs.claim_packs
    }


    issue_blocks = []


    for decision in revision_decisions.decisions:

        if not decision.requires_revision:
            continue


        if decision.target_agent != target_agent:
            continue


        verification = verification_by_claim.get(
            decision.claim
        )


        evidence_pack = evidence_by_claim.get(
            decision.claim
        )


        supported_parts = []

        unsupported_parts = []


        if verification:

            supported_parts = (
                verification.supported_parts
            )

            unsupported_parts = (
                verification.unsupported_parts
            )


        # =================================================
        # Compact Evidence
        # =================================================

        evidence_text = []


        if evidence_pack:

            for index, item in enumerate(
                evidence_pack.evidence[:2],
                start=1
            ):

                evidence_text.append(
                    f"""
Evidence {index}:
Source: {item.source_name}
Organization: {item.organization}

Text:
{item.text[:700]}
"""
                )


        block = f"""
=================================================
CLAIM REQUIRING REVISION
=================================================

Claim:
{decision.claim}

Verifier Verdict:
{decision.verdict}

Gate Action:
{decision.action}

Reason:
{decision.reason}

Directly Supported Parts:
{supported_parts}

Unsupported / Unverified Parts:
{unsupported_parts}

Relevant Retrieved Evidence:
{''.join(evidence_text)}
"""


        issue_blocks.append(
            block
        )


    return "\n".join(
        issue_blocks
    )


# =========================================================
# OpenAI Revision Call
# =========================================================

def revise_structured_output(
    current_output,
    output_model,
    schema_name: str,
    target_agent: str,
    revision_context: str
):

    """
    Perform a minimal targeted revision while
    preserving unaffected content.
    """

    schema = (
        output_model
        .model_json_schema()
    )


    current_json = (
        current_output
        .model_dump_json(
            indent=2
        )
    )


    system_prompt = """
You are the Targeted Revision Agent inside GameHive.

Your job is to make MINIMAL corrections to an existing
structured game-design output after cultural evidence
verification.

You are NOT creating a new game.

You are NOT rewriting the entire output.

You must preserve all unaffected content.


=====================================================
CORE REVISION RULE
=====================================================

Change ONLY content necessary to resolve the supplied
verification problems.

Everything unrelated to the failed claims should remain
as close as possible to the existing output.


=====================================================
EVIDENCE RULE
=====================================================

Use ONLY the verification information and evidence
provided to you.

Do not use outside cultural or historical knowledge.

Do not invent a new cultural fact to replace an
unsupported cultural fact.


=====================================================
VERDICT HANDLING
=====================================================

If a claim is PARTIALLY_SUPPORTED:

- preserve the supported portion
- remove, soften, or generalize the unsupported portion


If a claim is UNSUPPORTED:

- remove the unsupported factual presentation
OR
- clearly turn it into fictional content when appropriate


If a claim remains INSUFFICIENT after evidence retry:

- do not present it as authentic cultural or historical fact
- use neutral or generic wording
- or remove the unsupported factual detail


=====================================================
IMPORTANT
=====================================================

Do NOT:

- invent new characters
- invent new historical events
- invent new traditions
- invent new heritage facts
- invent new archaeological claims
- introduce new named locations as real places
- add new mechanics unless revising gameplay requires
  wording around an existing mechanic
- change unrelated fields


=====================================================
TARGET AGENT
=====================================================

You are revising the output belonging to:

TARGET_AGENT_PLACEHOLDER


Return the COMPLETE revised structured object required
by the supplied JSON schema.

Even though only a small part may change, return all
required fields.
""".replace(
        "TARGET_AGENT_PLACEHOLDER",
        target_agent
    )


    user_prompt = f"""
CURRENT OUTPUT:

{current_json}


TARGETED REVISION ISSUES:

{revision_context}


TASK:

Correct ONLY the affected content.

Preserve everything else.

Return the complete revised structured output.
"""


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

                "name": schema_name,

                "schema": schema,

                "strict": True
            }
        },

        store=False
    )


    raw_output = response.output_text


    if not raw_output:

        raise RuntimeError(
            f"OpenAI returned an empty "
            f"targeted revision response "
            f"for {target_agent}."
        )


    try:

        data = json.loads(
            raw_output
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            f"Targeted revision returned "
            f"invalid JSON for {target_agent}."
        ) from error


    return output_model(
        **data
    )


# =========================================================
# Apply Targeted Revisions
# =========================================================

def apply_targeted_revisions(
    state: GameState,
    revision_decisions: RevisionGateOutput,
    verification_results: CultureVerificationOutput,
    evidence_packs: EvidencePackOutput
):

    """
    Route revision problems back to the responsible
    game-design output.

    Only outputs that actually require revision
    are sent to OpenAI.
    """

    revised_agents = []

    targeted_claims = []


    # =====================================================
    # Collect Claims
    # =====================================================

    for decision in revision_decisions.decisions:

        if decision.requires_revision:

            targeted_claims.append(
                decision.claim
            )


    # =====================================================
    # Story Revision
    # =====================================================

    story_context = build_revision_context(
        target_agent="story_agent",
        revision_decisions=revision_decisions,
        verification_results=verification_results,
        evidence_packs=evidence_packs
    )


    if story_context.strip():

        print(
            "\nTargeted revision: story_agent..."
        )


        state.story = revise_structured_output(

            current_output=state.story,

            output_model=StoryOutput,

            schema_name="revised_story_output",

            target_agent="story_agent",

            revision_context=story_context
        )


        revised_agents.append(
            "story_agent"
        )


    # =====================================================
    # Gameplay Revision
    # =====================================================

    gameplay_context = build_revision_context(
        target_agent="gameplay_agent",
        revision_decisions=revision_decisions,
        verification_results=verification_results,
        evidence_packs=evidence_packs
    )


    if gameplay_context.strip():

        print(
            "\nTargeted revision: gameplay_agent..."
        )


        state.gameplay = revise_structured_output(

            current_output=state.gameplay,

            output_model=GameplayOutput,

            schema_name="revised_gameplay_output",

            target_agent="gameplay_agent",

            revision_context=gameplay_context
        )


        revised_agents.append(
            "gameplay_agent"
        )


    # =====================================================
    # Level Design Revision
    # =====================================================

    level_context = build_revision_context(
        target_agent="level_design_agent",
        revision_decisions=revision_decisions,
        verification_results=verification_results,
        evidence_packs=evidence_packs
    )


    if level_context.strip():

        print(
            "\nTargeted revision: level_design_agent..."
        )


        state.levels = revise_structured_output(

            current_output=state.levels,

            output_model=LevelDesignOutput,

            schema_name="revised_level_design_output",

            target_agent="level_design_agent",

            revision_context=level_context
        )


        revised_agents.append(
            "level_design_agent"
        )


    # =====================================================
    # Report
    # =====================================================

    report = TargetedRevisionReport(

        revised_agents=revised_agents,

        targeted_claims=targeted_claims,

        revision_count=len(
            targeted_claims
        )
    )


    return (
        state,
        report
    )


# =========================================================
# Print Revision Report
# =========================================================

def print_targeted_revision_report(
    report: TargetedRevisionReport
):

    print(
        "\n================================="
    )

    print(
        "GAMEHIVE TARGETED REVISION"
    )

    print(
        "================================="
    )


    print(
        f"Claims Targeted: "
        f"{report.revision_count}"
    )


    print(
        f"Agents Revised: "
        f"{len(report.revised_agents)}"
    )


    if report.revised_agents:

        print(
            "\nRevised Agents:"
        )

        for agent in report.revised_agents:

            print(
                "-",
                agent
            )


    if report.targeted_claims:

        print(
            "\nTargeted Claims:"
        )

        for claim in report.targeted_claims:

            print(
                "-",
                claim
            )
