from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel

from dndyo.app.models.actor import ActorRead
from dndyo.app.models.live_actor import LiveActorCreate, LiveActorRead


class GameStateBase(SQLModel):
    current_map_id: int = Field(foreign_key="map.id")
    environment_description: str = Field(
        default="",
        sa_column=Column("time", String, nullable=False, default=""),
    )


class GameState(GameStateBase, table=True):
    # `id` is the owning game id (GameState.id == Game.id).
    id: int = Field(primary_key=True, foreign_key="game.id")


class GameStateCreate(BaseModel):
    live_actors: list[LiveActorCreate] = PydanticField(default_factory=list)
    current_map_id: int | None = None
    environment_description: str = ""


class LiveActorWithDataRead(LiveActorRead):
    actor: ActorRead


class GameStateRead(BaseModel):
    live_actors: list[LiveActorWithDataRead]
    current_map_id: int
    environment_description: str


class LiveActorsUpdate(BaseModel):
    live_actors: list[LiveActorCreate]


class CurrentMapUpdate(BaseModel):
    current_map_id: int


class EnvironmentDescriptionUpdate(BaseModel):
    environment_description: str
