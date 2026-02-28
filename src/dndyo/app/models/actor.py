from typing import Optional
from enum import Enum
from sqlmodel import SQLModel, Field


class Size(str, Enum):
    tiny = "Tiny"
    small = "Small"
    medium = "Medium"
    large = "Large"
    huge = "Huge"
    gargantuan = "Gargantuan"


class Alignment(str, Enum):
    lawful_good = "Lawful Good"
    neutral_good = "Neutral Good"
    chaotic_good = "Chaotic Good"
    lawful_neutral = "Lawful Neutral"
    true_neutral = "Neutral"
    chaotic_neutral = "Chaotic Neutral"
    lawful_evil = "Lawful Evil"
    neutral_evil = "Neutral Evil"
    chaotic_evil = "Chaotic Evil"


class ActorBase(SQLModel):
    # Identity
    name: str = Field(index=True)
    level: int = Field(ge=1, le=20)

    # Core combat stats
    armor_class: int = Field(ge=0)
    hit_points: int = Field(ge=1)
    speed: int = Field(default=30, ge=0)

    # Ability scores (1–30 per 5e rules)
    strength: int = Field(ge=1, le=30)
    dexterity: int = Field(ge=1, le=30)
    constitution: int = Field(ge=1, le=30)
    intelligence: int = Field(ge=1, le=30)
    wisdom: int = Field(ge=1, le=30)
    charisma: int = Field(ge=1, le=30)

    # Meta
    proficiency_bonus: int = Field(ge=2, le=9)
    size: Size = Field(default=Size.medium)
    alignment: Alignment = Field(default=Alignment.true_neutral)

    # Game stuff
    controlled_by_user: bool = False
    can_fight: bool = False
    image_id: int = Field(foreign_key="image.id")


class Actor(ActorBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id", index=True)


class ActorCreate(ActorBase):
    pass


class ActorRead(ActorBase):
    id: int
