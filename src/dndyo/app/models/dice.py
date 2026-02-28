from typing import List
from pydantic import BaseModel


class DiceRollBase(BaseModel):
    dice_faces: int
    num_dices: int


class DiceRollCreate(DiceRollBase):
    pass


class DiceRollRead(BaseModel):
    outcome: List[int]
