from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class GameBase(SQLModel):
    name: str = Field(description="Display name of the game/campaign.")
    owner_user: str = Field(description="Temporary owner identifier.")
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
    pass


class GameRead(GameBase):
    id: int
