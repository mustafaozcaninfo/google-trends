"""Normalize user/motor seeds — optional single-word roots for autocomplete mining."""

from motors import MOTOR_FREE, MOTORS, MOTOR_ROOTS


def parse_seed_input(
    motor_name: str,
    extra: str,
    *,
    root_words: bool,
    include_motor_pack: bool = True,
) -> list[str]:
    seeds: list[str] = []
    use_pack = include_motor_pack and motor_name not in (MOTOR_FREE, "", None) and motor_name in MOTORS
    if use_pack:
        seeds.extend(MOTORS[motor_name])
    if root_words and use_pack and motor_name in MOTOR_ROOTS:
        seeds.extend(MOTOR_ROOTS[motor_name])
    if extra.strip():
        for part in extra.split(","):
            part = " ".join(part.split())
            if part:
                seeds.append(part)
    # Preserve order, dedupe
    out: list[str] = []
    seen: set[str] = set()
    for s in seeds:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out[:12]
