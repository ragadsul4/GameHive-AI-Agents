from pydantic import BaseModel, ConfigDict
from typing import Optional


class StoryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    premise: str
    characters: list[str]
    motivations: list[str]
    central_conflict: str
    world_setting: str
    narrative_tone: str


class GameplayOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    core_gameplay_loop: str
    key_mechanics: list[str]
    progression_system: str
    win_condition: str
    lose_condition: str


class LevelDesignOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level_names: list[str]
    level_settings: list[str]
    key_challenges: list[str]
    mechanic_focus: list[str]
    progression_purpose: list[str]


class GameState(BaseModel):
    game_idea: str

    story: Optional[StoryOutput] = None
    gameplay: Optional[GameplayOutput] = None
    levels: Optional[LevelDesignOutput] = None