from pydantic import BaseModel
from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel

from dndyo.app.models.live_actor import LiveActorCreate


class GameStateBase(SQLModel):
    current_map_id: int | None = Field(default=None, foreign_key="map.id")
    world_state: str = Field(
        default="",
        sa_column=Column("time", String, nullable=False, default=""),
    )


class GameState(GameStateBase, table=True):
    # `id` is the owning game id (GameState.id == Game.id).
    id: int = Field(primary_key=True, foreign_key="game.id")


class GameStateRead(BaseModel):
    live_actors: list[LiveActorCreate]
    current_map_id: int | None
    world_state: str


class LiveActorsUpdate(BaseModel):
    live_actors: list[LiveActorCreate]


class CurrentMapUpdate(BaseModel):
    current_map_id: int | None


class WorldStateUpdate(BaseModel):
    world_state: str
