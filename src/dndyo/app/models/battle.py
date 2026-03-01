from pydantic import BaseModel, Field


class LiveActorAttackCreate(BaseModel):
    live_actor_id: int = Field(ge=1, description="ID of the live actor being attacked.")
    attack_bonus: int = Field(
        default=0,
        description="Static modifier added to the d20 attack roll.",
    )
    damage_num_dice: int = Field(
        default=1,
        ge=1,
        description="How many damage dice to roll on hit.",
    )
    damage_dice_faces: int = Field(
        default=6,
        ge=2,
        description="Number of faces per damage die (e.g. 6 for d6).",
    )
    damage_bonus: int = Field(
        default=0,
        description="Static modifier added to rolled damage.",
    )


class LiveActorAttackRead(BaseModel):
    live_actor_id: int = Field(description="Live actor ID that received the attack.")
    actor_id: int = Field(description="Base actor ID associated with the live actor.")
    attack_roll: int = Field(description="Raw d20 attack roll.")
    total_to_hit: int = Field(description="attack_roll + attack_bonus.")
    critical: bool = Field(description="True when attack roll is a natural 20.")
    hit: bool = Field(description="True when the attack hits the target.")
    damage_rolls: list[int] = Field(
        default_factory=list,
        description="Individual damage dice outcomes (empty when attack misses).",
    )
    damage: int = Field(description="Final applied damage after modifiers/critical.")
    remaining_hp: int = Field(description="Target HP after damage application.")
