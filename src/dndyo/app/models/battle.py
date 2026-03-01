from pydantic import BaseModel, Field


class LiveActorAttackCreate(BaseModel):
    live_actor_id: int = Field(ge=1)
    attack_bonus: int = 0
    damage_num_dice: int = Field(default=1, ge=1)
    damage_dice_faces: int = Field(default=6, ge=2)
    damage_bonus: int = 0


class LiveActorAttackRead(BaseModel):
    live_actor_id: int
    actor_id: int
    attack_roll: int
    total_to_hit: int
    critical: bool
    hit: bool
    damage_rolls: list[int]
    damage: int
    remaining_hp: int
