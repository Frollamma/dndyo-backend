import pytest

from dndyo.app.helpers.battle import (
    ability_modifier,
    apply_damage,
    apply_healing,
    calculate_damage_from_roll,
    is_critical_hit,
    is_critical_miss,
    resolve_attack_roll,
)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (1, -5),
        (8, -1),
        (10, 0),
        (12, 1),
        (20, 5),
        (30, 10),
    ],
)
def test_ability_modifier(score, expected):
    assert ability_modifier(score) == expected


def test_critical_helpers():
    assert is_critical_hit(20) is True
    assert is_critical_hit(19) is False
    assert is_critical_hit(19, critical_threshold=19) is True
    assert is_critical_miss(1) is True
    assert is_critical_miss(2) is False


def test_resolve_attack_roll_critical_miss_overrides_total():
    result = resolve_attack_roll(
        attack_roll=1,
        attack_bonus=50,
        target_armor_class=10,
    )
    assert result.critical_miss is True
    assert result.critical is False
    assert result.total_to_hit == 51
    assert result.hit is False


def test_resolve_attack_roll_critical_hit():
    result = resolve_attack_roll(
        attack_roll=20,
        attack_bonus=-5,
        target_armor_class=30,
    )
    assert result.critical is True
    assert result.critical_miss is False
    assert result.hit is True


def test_resolve_attack_roll_normal_hit_and_miss():
    hit = resolve_attack_roll(
        attack_roll=12,
        attack_bonus=3,
        target_armor_class=15,
    )
    miss = resolve_attack_roll(
        attack_roll=11,
        attack_bonus=3,
        target_armor_class=15,
    )
    assert hit.hit is True
    assert miss.hit is False


def test_calculate_damage_from_roll_regular_and_critical():
    assert calculate_damage_from_roll(rolled_damage=7, damage_bonus=2, critical=False) == 9
    assert calculate_damage_from_roll(rolled_damage=7, damage_bonus=2, critical=True) == 16


def test_calculate_damage_from_roll_never_negative():
    assert calculate_damage_from_roll(rolled_damage=0, damage_bonus=-5, critical=False) == 0


def test_apply_damage_clamps_at_zero_and_ignores_negative_damage():
    assert apply_damage(current_hp=12, damage=5) == 7
    assert apply_damage(current_hp=12, damage=99) == 0
    assert apply_damage(current_hp=12, damage=-4) == 12


def test_apply_healing_with_and_without_max_hp():
    assert apply_healing(current_hp=5, heal_amount=4) == 9
    assert apply_healing(current_hp=5, heal_amount=-2) == 5
    assert apply_healing(current_hp=8, heal_amount=10, max_hp=12) == 12
