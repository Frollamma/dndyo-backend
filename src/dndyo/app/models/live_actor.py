from enum import Enum
from typing import List
from sqlalchemy import JSON
from dndyo.app.models.inventory_object import InventoryObject
from sqlmodel import SQLModel, Field


class LiveActorRole(str, Enum):
    player = "Player"
    enemy = "Enemy"
    npc = "NPC"


class LiveActorBase(SQLModel):
    actor_id: int = Field(foreign_key="actor.id")
    current_hp: int = Field(ge=0)
    state: str
    background: str = Field(
        default="",
        description="Unique description and history for this live actor.",
    )
    role: LiveActorRole
    inventory: List[InventoryObject] = Field(default_factory=list, sa_type=JSON)


class LiveActor(LiveActorBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id", index=True)


class LiveActorCreate(LiveActorBase):
    pass


class LiveActorRead(LiveActorBase):
    id: int
