from typing import List, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class MapBase(SQLModel):
    name: str
    description: int
    # Optional image for the map.
    image_id: Optional[int] = Field(default=None, foreign_key="image.id")
    connected_maps_ids: List[int] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )


class Map(MapBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id", index=True)


class MapCreate(MapBase):
    pass


class MapRead(MapBase):
    id: int
