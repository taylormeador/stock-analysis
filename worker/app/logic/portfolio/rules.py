import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable

import numpy as np

from app.logic.portfolio.ewmac import run_ewmac_variation
from app.logic.portfolio.tables import (
    asset_class_region_correlations,
    asset_correlations,
    bond_correlations,
    carry_correlations,
    diversification_multipliers,
    ewmac_correlations,
    rule_correlations,
    sub_asset_class_region_correlations,
    sub_asset_correlations,
    super_asset_correlations,
)

logger = logging.getLogger(__name__)


class Rule(Enum):
    EWMAC = "ewmac"
    CARRY = "carry"


@dataclass
class RuleVariation:
    rule: Rule
    description: str
    forecaster: Callable


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
        description="EWMAC fast 8 slow 32 - Captures shorter term trends",
        forecaster=run_ewmac_variation,
    ),
    "ewmac_16_64": RuleVariation(
        rule=Rule.EWMAC,
        description="EWMAC fast 16 slow 64 - Captures medium term trends",
        forecaster=run_ewmac_variation,
    ),
    "ewmac_32_128": RuleVariation(
        rule=Rule.EWMAC,
        description="EWMAC fast 32 slow 128 - Captures longer term trends",
        forecaster=run_ewmac_variation,
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


def calc_variation_weights(rule_names: list[str]) -> np.ndarray:
    """
    Derive forecast weights from Carver's correlation tables.

    Builds the correlation matrix from table 57, inverts it, and sums
    each row to get raw weights. Variations that are highly correlated
    with others get downweighted. Weights are clipped to zero and
    normalized to sum to 1.0.
    """
    n = len(rule_names)
    if n == 1:
        return np.array([1.0])

    corr_matrix = np.ones((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            corr = lookup_variation_correlation(rule_names[i], rule_names[j])
            corr_matrix[i, j] = corr
            corr_matrix[j, i] = corr

    inv_corr = np.linalg.inv(corr_matrix)
    raw_weights = inv_corr.sum(axis=1)
    raw_weights = np.clip(raw_weights, 0, None)
    return raw_weights / raw_weights.sum()


def lookup_variation_correlation(variation_a: str, variation_b: str) -> float:
    """
    Return the correlation between two variations.
    Same rules uses the rule-specific correlation table.
    Different rules use Carver's table 56 cross-style correlation of 0.25.
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


def calc_fdm(rule_names: list[str]) -> float:
    """
    Look up the Forecast Diversification Multiplier for a list of rule variations.
    Uses Carver's table 18 (forecast_diversification_multipliers) directly.

    Computes average pairwise correlation from table 57, then looks up the
    FDM from table 18 based on number of rules and that average correlation.
    Capped at 2.5 per Carver's recommendation.
    """
    n = len(rule_names)
    if n == 1:
        return 1.0

    # Compute average pairwise correlation from table 57
    pairwise = []
    for i in range(n):
        for j in range(i + 1, n):
            pairwise.append(lookup_variation_correlation(rule_names[i], rule_names[j]))
    avg_corr = np.mean(pairwise)

    # Lookup FDM in table 18
    n_values = diversification_multipliers["num_assets"].values
    corr_cols = np.array([0.0, 0.25, 0.5, 0.75, 1.0])

    closest_n = int(n_values[n_values <= n][-1])
    closest_corr = float(corr_cols[corr_cols <= avg_corr][-1])

    row = diversification_multipliers[
        diversification_multipliers["num_assets"] == closest_n
    ].iloc[0]

    return min(float(row[closest_corr]), 2.5)


def lookup_instrument_correlation(a: dict, b: dict) -> float:
    SYSTEMATIC_TRADER_ADJUSTMENT = 0.7

    sac_a = a["super_asset_class"]
    sac_b = b["super_asset_class"]
    ac_a = a["asset_class"]
    ac_b = b["asset_class"]
    sub_a = a["sub_asset_class"]
    sub_b = b["sub_asset_class"]
    reg_a = a["region"]
    reg_b = b["region"]

    # Both rates — use table 55 (bond duration correlations)
    if sac_a == "rates" and sac_b == "rates":
        indexed = bond_correlations.set_index("asset")
        if sub_a == sub_b:
            return 1.0 * SYSTEMATIC_TRADER_ADJUSTMENT
        for row_key, col_key in [(sub_a, sub_b), (sub_b, sub_a)]:
            try:
                val = indexed.loc[row_key, col_key]
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    return float(val) * SYSTEMATIC_TRADER_ADJUSTMENT
            except KeyError:
                continue
        logger.warning(f"Bond correlation not found for {sub_a} vs {sub_b}, using 0.5")
        return 0.5 * SYSTEMATIC_TRADER_ADJUSTMENT

    # Same super_asset_class
    if sac_a == sac_b:
        # Same sub_asset_class
        if sub_a == sub_b:
            # Same region — use table 54
            if reg_a is not None and reg_a == reg_b:
                indexed = sub_asset_class_region_correlations.set_index("asset")
                if ac_a in indexed.index:
                    return (
                        float(indexed.loc[ac_a, "correlation"])
                        * SYSTEMATIC_TRADER_ADJUSTMENT
                    )

            # Different region — use table 53
            indexed = asset_class_region_correlations.set_index("asset")
            if ac_a in indexed.index:
                return (
                    float(indexed.loc[ac_a, "correlation"])
                    * SYSTEMATIC_TRADER_ADJUSTMENT
                )

        # Different sub_asset_class within same super class
        # Commodities — use table 52
        if sac_a == "commodities":
            indexed = sub_asset_correlations.set_index("asset")
            for row_key, col_key in [(sub_a, sub_b), (sub_b, sub_a)]:
                try:
                    val = indexed.loc[row_key, col_key]
                    if val is not None and not (
                        isinstance(val, float) and np.isnan(val)
                    ):
                        return float(val) * SYSTEMATIC_TRADER_ADJUSTMENT
                except KeyError:
                    continue

        # Financials (rates, equities, fx) — use table 51
        indexed = asset_correlations.set_index("asset")
        for row_key, col_key in [(ac_a, ac_b), (ac_b, ac_a)]:
            try:
                val = indexed.loc[row_key, col_key]
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    return float(val) * SYSTEMATIC_TRADER_ADJUSTMENT
            except KeyError:
                continue

    # Different super_asset_class — use table 50
    indexed = super_asset_correlations.set_index("asset")
    for row_key, col_key in [(sac_a, sac_b), (sac_b, sac_a)]:
        try:
            val = indexed.loc[row_key, col_key]
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                return float(val) * SYSTEMATIC_TRADER_ADJUSTMENT
        except KeyError:
            continue

    logger.warning(f"Correlation not found for {sac_a} vs {sac_b}, using 0.25")
    return 0.25


def calc_idm(instruments: list[dict]) -> float:
    """
    Calculate the Instrument Diversification Multiplier using Carver's table 18.

    Takes the full instrument metadata dicts so correlations can be looked up
    from the appropriate table in the hierarchy. Uses equal weights across
    instruments and the same floor lookup as calc_fdm. Capped at 2.5.
    """
    n = len(instruments)
    if n == 1:
        return 1.0

    pairwise = []
    for i in range(n):
        for j in range(i + 1, n):
            pairwise.append(
                lookup_instrument_correlation(instruments[i], instruments[j])
            )
    avg_corr = float(np.mean(pairwise))

    n_values = diversification_multipliers["num_assets"].values
    corr_cols = np.array([0.0, 0.25, 0.5, 0.75, 1.0])

    closest_n = int(n_values[n_values <= n][-1])
    closest_corr = float(corr_cols[corr_cols <= avg_corr][-1])

    row = diversification_multipliers[
        diversification_multipliers["num_assets"] == closest_n
    ].iloc[0]

    return min(float(row[closest_corr]), 2.5)
