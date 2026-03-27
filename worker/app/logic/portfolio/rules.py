import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable

import numpy as np
from sqlalchemy import text

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
    name: str
    rule: Rule
    description: str
    forecaster: Callable


class VariationRegistry:
    """
    Loads active rule variations from the database and resolves their
    forecaster callables. Raises ValueError on init if any active variation
    references a rule with no registered callable.

    Usage (once per task invocation):
        with db.get_connection() as conn:
            registry = VariationRegistry.load(conn)
    """

    def __init__(self, variations: list[RuleVariation]):
        self._variations: dict[str, RuleVariation] = {v.name: v for v in variations}

    @classmethod
    def load(cls, conn) -> "VariationRegistry":
        """
        Query active variations from the DB, resolve callables, and return
        a populated VariationRegistry. Raises ValueError if any active
        variation's rule has no registered callable.
        """
        sql = text("""
            SELECT name, rule, description
            FROM rule_variations
            WHERE is_active = TRUE
            ORDER BY name
        """)
        rows = conn.execute(sql).fetchall()

        if not rows:
            raise RuntimeError("No active variations found in rule_variations table")

        forecasters: dict[str, Callable] = {
            "ewmac": run_ewmac_variation,
            # "carry": run_carry_variation,  # uncomment when carry is implemented
        }
        variations = []
        for row in rows:
            forecaster_ = forecasters.get(row.rule)
            if forecaster_ is None:
                raise ValueError(
                    f"Variation '{row.name}' references rule '{row.rule}' "
                    f"which has no registered callable. "
                    f"Registered rules: {list(forecasters.keys())}"
                )
            try:
                rule_enum = Rule(row.rule)
            except ValueError:
                raise ValueError(
                    f"Variation '{row.name}' has unknown rule '{row.rule}'. "
                    f"Known rules: {[r.value for r in Rule]}"
                )
            variations.append(
                RuleVariation(
                    name=row.name,
                    rule=rule_enum,
                    description=row.description,
                    forecaster=forecaster_,
                )
            )

        logger.info(
            f"Loaded {len(variations)} active variations from DB: "
            f"{[v.name for v in variations]}"
        )
        return cls(variations)

    def all(self) -> list[RuleVariation]:
        return list(self._variations.values())

    def names(self) -> list[str]:
        return list(self._variations.keys())

    def get(self, name: str) -> RuleVariation:
        if name not in self._variations:
            raise ValueError(
                f"Unknown variation '{name}'. Active variations: {self.names()}"
            )
        return self._variations[name]


# ── Correlation helpers ───────────────────────────────────────────────────────


def lookup_same_rule_correlation(
    rule: Rule,
    variation_a: str,
    variation_b: str,
) -> float:
    if rule == Rule.EWMAC:
        indexed = ewmac_correlations
    elif rule == Rule.CARRY:
        indexed = carry_correlations
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


def lookup_variation_correlation(
    variation_a: str,
    variation_b: str,
    registry: "VariationRegistry",
) -> float:
    """
    Return the correlation between two variations.
    Same rule uses the rule-specific correlation table.
    Different rules use Carver's table 56 cross-style correlation of 0.25.
    """
    var_a = registry.get(variation_a)
    var_b = registry.get(variation_b)

    if var_a.rule == var_b.rule:
        return lookup_same_rule_correlation(var_a.rule, variation_a, variation_b)

    return float(rule_correlations.loc["different_styles", "correlation"])


def calc_variation_weights(
    rule_names: list[str], registry: "VariationRegistry"
) -> np.ndarray:
    """
    Derive forecast weights from Carver's correlation tables.
    """
    n = len(rule_names)
    if n == 1:
        return np.array([1.0])

    corr_matrix = np.ones((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            corr = lookup_variation_correlation(rule_names[i], rule_names[j], registry)
            corr_matrix[i, j] = corr
            corr_matrix[j, i] = corr

    inv_corr = np.linalg.inv(corr_matrix)
    raw_weights = inv_corr.sum(axis=1)
    raw_weights = np.clip(raw_weights, 0, None)
    return raw_weights / raw_weights.sum()


def calc_fdm(rule_names: list[str], registry: "VariationRegistry") -> float:
    """
    Look up the Forecast Diversification Multiplier for a list of rule variations.
    Capped at 2.5 per Carver's recommendation.
    """
    n = len(rule_names)
    if n == 1:
        return 1.0

    pairwise = []
    for i in range(n):
        for j in range(i + 1, n):
            pairwise.append(
                lookup_variation_correlation(rule_names[i], rule_names[j], registry)
            )
    avg_corr = np.mean(pairwise)

    n_values = diversification_multipliers.index.values
    corr_cols = np.array(diversification_multipliers.columns.values, dtype=float)

    closest_n = int(n_values[n_values <= n][-1])
    closest_corr = float(corr_cols[corr_cols <= avg_corr][-1])

    return min(float(diversification_multipliers.loc[closest_n, closest_corr]), 2.5)


def lookup_instrument_correlation(a: dict, b: dict) -> float:
    """
    Return the correlation between two instrument trading subsystems using
    Carver's hierarchy of correlation tables (tables 50-55), multiplied by
    0.7 per Carver's recommendation for systematic traders.
    """
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
        if sub_a == sub_b:
            return 1.0 * SYSTEMATIC_TRADER_ADJUSTMENT
        for row_key, col_key in [(sub_a, sub_b), (sub_b, sub_a)]:
            try:
                val = bond_correlations.loc[row_key, col_key]
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    return float(val) * SYSTEMATIC_TRADER_ADJUSTMENT
            except KeyError:
                continue
        logger.warning(f"Bond correlation not found for {sub_a} vs {sub_b}, using 0.5")
        return 0.5 * SYSTEMATIC_TRADER_ADJUSTMENT

    # Same super_asset_class
    if sac_a == sac_b:
        if sub_a == sub_b:
            if reg_a is not None and reg_a == reg_b:
                if ac_a in sub_asset_class_region_correlations.index:
                    return (
                        float(
                            sub_asset_class_region_correlations.loc[ac_a, "correlation"]
                        )
                        * SYSTEMATIC_TRADER_ADJUSTMENT
                    )
            if ac_a in asset_class_region_correlations.index:
                return (
                    float(asset_class_region_correlations.loc[ac_a, "correlation"])
                    * SYSTEMATIC_TRADER_ADJUSTMENT
                )

        if sac_a == "commodities":
            for row_key, col_key in [(sub_a, sub_b), (sub_b, sub_a)]:
                try:
                    val = sub_asset_correlations.loc[row_key, col_key]
                    if val is not None and not (
                        isinstance(val, float) and np.isnan(val)
                    ):
                        return float(val) * SYSTEMATIC_TRADER_ADJUSTMENT
                except KeyError:
                    continue

        for row_key, col_key in [(ac_a, ac_b), (ac_b, ac_a)]:
            try:
                val = asset_correlations.loc[row_key, col_key]
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    return float(val) * SYSTEMATIC_TRADER_ADJUSTMENT
            except KeyError:
                continue

    # Different super_asset_class — use table 50
    for row_key, col_key in [(sac_a, sac_b), (sac_b, sac_a)]:
        try:
            val = super_asset_correlations.loc[row_key, col_key]
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                return float(val) * SYSTEMATIC_TRADER_ADJUSTMENT
        except KeyError:
            continue

    logger.warning(f"Correlation not found for {sac_a} vs {sac_b}, using 0.25")
    return 0.25


def calc_idm(instruments: list[dict]) -> float:
    """
    Calculate the Instrument Diversification Multiplier using Carver's table 18.
    Capped at 2.5.
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

    n_values = diversification_multipliers.index.values
    corr_cols = np.array(diversification_multipliers.columns.values, dtype=float)

    closest_n = int(n_values[n_values <= n][-1])
    closest_corr = float(corr_cols[corr_cols <= avg_corr][-1])

    return min(float(diversification_multipliers.loc[closest_n, closest_corr]), 2.5)
