from .models import OpportunityDirection, ScoreFactor


def explain(
    symbol: str,
    direction: OpportunityDirection,
    eligible: bool,
    factors: list[ScoreFactor],
    hard_gates: list[str],
) -> tuple[list[str], list[str], str]:
    ordered = sorted(
        factors,
        key=lambda item: (-item.weighted_contribution, item.factor_name.value),
    )
    strongest = [item.factor_name.value for item in ordered[:3]]
    weakest = [
        item.factor_name.value
        for item in sorted(
            factors,
            key=lambda item: (item.normalized_score, item.factor_name.value),
        )[:3]
    ]
    if not eligible:
        return (
            strongest,
            weakest,
            f"{symbol} is excluded from ranking by deterministic hard gates: "
            + "; ".join(hard_gates)
            + ".",
        )
    positive = ", ".join(name.replace("_", " ") for name in strongest)
    negative = ", ".join(name.replace("_", " ") for name in weakest)
    return (
        strongest,
        weakest,
        (
            f"{symbol} has {direction.value} analytical evidence led by {positive}. "
            f"The weakest measured areas are {negative}. This is setup quality for further "
            "evaluation, not a trade instruction."
        ),
    )
