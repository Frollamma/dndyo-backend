import random
from fastapi import APIRouter, Depends
from dndyo.app.models.dice import DiceRollCreate, DiceRollRead
from dndyo.app.routers.game.deps import require_game_id

router = APIRouter()


@router.post("/roll", response_model=DiceRollRead)
def roll_dice(
    roll: DiceRollCreate,
):
    outcome = [random.randint(1, roll.dice_faces) for _ in range(roll.num_dices)]

    return DiceRollRead(
        outcome=outcome,
    )
