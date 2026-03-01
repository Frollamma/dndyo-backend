from dataclasses import dataclass


@dataclass(frozen=True)
class AttackRollResult:
    hit: bool
    critical: bool
    critical_miss: bool
    total_to_hit: int


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def is_critical_hit(attack_roll: int, critical_threshold: int = 20) -> bool:
    return attack_roll >= critical_threshold


def is_critical_miss(attack_roll: int) -> bool:
    return attack_roll == 1


def resolve_attack_roll(
    *,
    attack_roll: int,
    attack_bonus: int,
    target_armor_class: int,
    critical_threshold: int = 20,
) -> AttackRollResult:
    critical = is_critical_hit(attack_roll, critical_threshold)
    critical_miss = is_critical_miss(attack_roll)
    total_to_hit = attack_roll + attack_bonus
    hit = False if critical_miss else (critical or total_to_hit >= target_armor_class)
    return AttackRollResult(
        hit=hit,
        critical=critical,
        critical_miss=critical_miss,
        total_to_hit=total_to_hit,
    )


def calculate_damage_from_roll(
    *,
    rolled_damage: int,
    damage_bonus: int = 0,
    critical: bool = False,
) -> int:
    # DnD 5e rule: on a critical hit, roll all attack damage dice twice.
    # Here we receive the already rolled total, so we double only that component.
    dice_damage = rolled_damage * 2 if critical else rolled_damage
    return max(0, dice_damage + damage_bonus)


def apply_damage(*, current_hp: int, damage: int) -> int:
    return max(0, current_hp - max(0, damage))


def apply_healing(*, current_hp: int, heal_amount: int, max_hp: int | None = None) -> int:
    healed = current_hp + max(0, heal_amount)
    if max_hp is None:
        return healed
    return min(max_hp, healed)
