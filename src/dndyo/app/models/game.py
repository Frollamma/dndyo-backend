from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from dndyo.app.models.game_state import GameStateCreate


class GameBase(SQLModel):
    name: str = Field(description="Display name of the game/campaign.")
    owner_user: str = Field(description="Temporary owner identifier.")
    ai_initial_prompt: str
    chapters: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Ordered list of all chapters available in this game.",
    )
    current_chapters: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Ordered list of chapters already unlocked.",
    )


class Game(GameBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # Points to the game state row. In practice this is the same value as `id`.
    game_state_id: int | None = Field(
        default=None,
        foreign_key="gamestate.id",
        description="Linked game state row id.",
    )


class GameCreate(GameBase):
    initial_state: GameStateCreate | None = Field(
        default=None,
        description="Optional initial game state (environment/map/live actors).",
    )


class GameRead(GameBase):
    id: int
