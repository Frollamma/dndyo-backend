from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class GameBase(SQLModel):
    name: str
    owner_user: str
    chapters: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    current_chapters: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class Game(GameBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # Points to the game state row. In practice this is the same value as `id`.
    game_state_id: int | None = Field(default=None, foreign_key="gamestate.id")


class GameCreate(GameBase):
    pass


class GameRead(GameBase):
    id: int
