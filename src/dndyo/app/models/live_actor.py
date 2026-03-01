from enum import Enum
from typing import List
from sqlalchemy import JSON, Column
from pydantic import field_validator
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
    # Store inventory as JSON in the DB. InventoryObject instances will be
    # converted to plain dicts by Pydantic when serializing via SQLModel.
    inventory: List[InventoryObject] = Field(
        default_factory=list, sa_column=Column(JSON)
    )

    @field_validator("inventory", mode="before")
    def _coerce_inventory(v):
        """Ensure inventory entries are primitive-serializable (dicts) before DB storage.

        Accepts InventoryObject instances (from tests) and converts them to dicts.
        """
        if v is None:
            return []
        coerced = []
        for item in v:
            if hasattr(item, "model_dump"):
                coerced.append(item.model_dump())
            elif hasattr(item, "dict"):
                # pydantic v1 compatibility
                coerced.append(item.dict())
            else:
                coerced.append(item)
        return coerced

    def __init__(self, **data):
        # Ensure inventory entries are converted to primitive dicts when
        # constructing the model (covers direct instantiation in tests).
        inv = data.get("inventory")
        if inv is not None:
            coerced = []
            for item in inv:
                if hasattr(item, "model_dump"):
                    coerced.append(item.model_dump())
                elif hasattr(item, "dict"):
                    coerced.append(item.dict())
                else:
                    coerced.append(item)
            data["inventory"] = coerced
        super().__init__(**data)


class LiveActor(LiveActorBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id", index=True)


class LiveActorCreate(LiveActorBase):
    pass


class LiveActorRead(LiveActorBase):
    id: int
