import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np

from app.logic.portfolio.tables import (
    ewmac_correlations,
    carry_correlations,
    rule_correlations,
)

logger = logging.getLogger(__name__)


class Rule(Enum):
    EWMAC = "ewmac"
    CARRY = "carry"


@dataclass
class RuleVariation:
    rule: Rule
    description: str


def lookup_same_rule_correlation(
    rule: Rule,
    variation_a: str,
    variation_b: str,
) -> float:
    if rule == Rule.EWMAC:
        indexed = ewmac_correlations.set_index("variation")
    elif rule == Rule.CARRY:
        indexed = carry_correlations.set_index("variation")
    else:
        logger.warning(f"No correlation table for {rule}, using 0.5")
        return 0.5

    for row_key, col_key in [(variation_a, variation_b), (variation_b, variation_a)]:
        try:
            val = indexed.loc[row_key, col_key]
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                return float(val)
        except KeyError:
            continue

    logger.warning(
        f"Correlation not found for {variation_a} vs {variation_b}, using 0.5"
    )
    return 0.5


VARIATION_REGISTRY: dict[str, RuleVariation] = {
    "ewmac_8_32": RuleVariation(
        rule=Rule.EWMAC,
        description="EWMAC fast 8 slow 32",
    ),
    "ewmac_16_64": RuleVariation(
        rule=Rule.EWMAC,
        description="EWMAC fast 16 slow 64",
    ),
    "ewmac_32_128": RuleVariation(
        rule=Rule.EWMAC,
        description="EWMAC fast 32 slow 128",
    ),
}


def get_variation(variation_name: str) -> RuleVariation:
    if variation_name not in VARIATION_REGISTRY:
        raise ValueError(
            f"Unknown rule '{variation_name}'. "
            f"Register it in VARIATION_REGISTRY before use. "
            f"Known variations: {list(VARIATION_REGISTRY.keys())}"
        )
    return VARIATION_REGISTRY[variation_name]


def lookup_correlation(variation_a: str, variation_b: str) -> float:
    """
    Return the correlation between two rules.
    Same family uses the family-specific correlation table.
    Different families use Carver's table 56 cross-style correlation of 0.25.
    """
    var_a = get_variation(variation_a)
    var_b = get_variation(variation_b)

    if var_a.rule == var_b.rule:
        return lookup_same_rule_correlation(var_a.rule, variation_a, variation_b)

    return float(
        rule_correlations.set_index(rule_correlations.columns[0]).loc[
            "different_styles", "correlation"
        ]
    )


def calc_fdm(rule_names: list[str], weights: np.ndarray) -> float:
    """
    Calculate the Forecast Diversification Multiplier for a list of rules.
    Capped at 2.5 per Carver's recommendation.

    Args:
        rule_names: list of rule name strings
        weights: array of weights, must sum to 1.0 and match length of rule_names
    """
    num_rules = len(rule_names)
    if num_rules == 1:
        return 1.0

    assert len(weights) == num_rules, "weights must match number of rules"
    assert abs(weights.sum() - 1.0) < 1e-6, "weights must sum to 1.0"

    corr_matrix = np.ones((num_rules, num_rules))
    for i in range(num_rules):
        for j in range(i + 1, num_rules):
            corr = lookup_correlation(rule_names[i], rule_names[j])
            corr_matrix[i, j] = corr
            corr_matrix[j, i] = corr

    fdm = 1.0 / np.sqrt(weights @ corr_matrix @ weights)
    return min(fdm, 2.5)
