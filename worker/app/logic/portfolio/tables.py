import pandas as pd
import numpy as np

# Table 18: diversification multiplier
# Carver recommends capping this at 2.5
diversification_multipliers = pd.DataFrame(
    index=[2, 3, 4, 5, 10, 15, 20, 50],
    columns=[0.0, 0.25, 0.5, 0.75, 1.0],
    data=[
        [1.41, 1.27, 1.15, 1.10, 1.0],
        [1.73, 1.41, 1.22, 1.12, 1.0],
        [2.0, 1.51, 1.27, 1.10, 1.0],
        [2.2, 1.58, 1.29, 1.15, 1.0],
        [3.2, 1.75, 1.35, 1.17, 1.0],
        [3.9, 1.83, 1.37, 1.17, 1.0],
        [4.5, 1.86, 1.38, 1.18, 1.0],
        [7.1, 1.94, 1.40, 1.19, 1.0],
    ],
)

# Table 50: Correlations of instrument returns across super-asset classes
_super_asset_labels = ["rates", "equities", "fx", "commodities", "vol"]
super_asset_correlations = pd.DataFrame(
    index=_super_asset_labels,
    columns=_super_asset_labels,
    data=[
        [1, 0.1, 0.1, 0.1, 0.1],
        [0.1, 1, 0.1, 0.1, 0.6],
        [0.1, 0.1, 1, 0.25, 0.2],
        [0.1, 0.1, 0.25, 1, 0.1],
        [0.1, 0.6, 0.2, 0.1, 1],
    ],
)

# Table 51: Correlation of instrument returns, across asset classes
_asset_labels = ["bonds", "STIR", "agricultural", "metal", "energy"]
asset_correlations = pd.DataFrame(
    index=_asset_labels,
    columns=_asset_labels,
    data=[
        [1, 0.5, np.nan, np.nan, np.nan],
        [0.5, 1, np.nan, np.nan, np.nan],
        [np.nan, np.nan, 1, 0.2, 0.25],
        [np.nan, np.nan, 0.2, 1, 0.35],
        [np.nan, np.nan, 0.25, 0.35, 1],
    ],
)

# Table 52: Correlation of instrument returns, by sub asset class, within commodity asset classes
_sub_asset_labels = [
    "grains",
    "softs",
    "livestock",
    "oil",
    "gas",
    "precious_metals",
    "base_metals",
]
sub_asset_correlations = pd.DataFrame(
    index=_sub_asset_labels,
    columns=_sub_asset_labels,
    data=[
        [1, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan],
        [0.4, 1, np.nan, np.nan, np.nan, np.nan, np.nan],
        [0.25, 0.15, 1, np.nan, np.nan, np.nan, np.nan],
        [np.nan, np.nan, np.nan, 1, 0.25, np.nan, np.nan],
        [np.nan, np.nan, np.nan, 0.25, 1, np.nan, np.nan],
        [np.nan, np.nan, np.nan, np.nan, np.nan, 1, 0.5],
        [np.nan, np.nan, np.nan, np.nan, np.nan, 0.5, 1],
    ],
)

# Table 53: Correlations of instrument returns for regions within financial asset classes
asset_class_region_correlations = pd.DataFrame(
    index=["bonds", "STIR", "equities", "col", "fx"],
    columns=["correlation"],
    data=[0.35, 0.35, 0.50, 0.50, 0.15],
)

# Table 54: Correlation of instrument returns, within regions and sub asset classes
sub_asset_class_region_correlations = pd.DataFrame(
    index=[
        "bonds",
        "equities_country",
        "fx",
        "vol",
        "commodities",
        "equities_industry",
        "equities_firm",
    ],
    columns=["correlation"],
    data=[0.35, 0.35, 0.50, 0.50, 0.15, 0.15, 0.15],
)

# Table 55: Correlation of instrument returns, for bonds of different duration in same country
_bond_duration_labels = ["2_year", "5_year", "10_year", "20_year", "30_year"]
bond_correlations = pd.DataFrame(
    index=_bond_duration_labels,
    columns=_bond_duration_labels,
    data=[
        [1, np.nan, np.nan, np.nan, np.nan],
        [0.8, 1, np.nan, np.nan, np.nan],
        [0.65, 0.85, 1, np.nan, np.nan],
        [0.5, 0.80, 0.85, 1, np.nan],
        [0.5, 0.75, 0.80, 0.90, 1],
    ],
)

# Table 56: Correlation of trading rule returns within an instrument
rule_correlations = pd.DataFrame(
    index=["different_styles", "different_rules"],
    columns=["correlation"],
    data=[0.25, 0.5],
)

# Table 57: Correlation of trading rule returns within an instrument, variations on EWMAC rule
_ewmac_labels = [
    "ewmac_2_8",
    "ewmac_4_16",
    "ewmac_8_32",
    "ewmac_16_64",
    "ewmac_32_128",
    "ewmac_64_256",
]
ewmac_correlations = pd.DataFrame(
    index=_ewmac_labels,
    columns=_ewmac_labels,
    data=[
        [1, np.nan, np.nan, np.nan, np.nan, np.nan],
        [0.9, 1, np.nan, np.nan, np.nan, np.nan],
        [0.6, 0.9, 1, np.nan, np.nan, np.nan],
        [0.35, 0.60, 0.90, 1, np.nan, np.nan],
        [0.2, 0.4, 0.65, 0.90, 1, np.nan],
        [0.15, 0.2, 0.45, 0.70, 0.90, 1],
    ],
)

# TODO implement carry
carry_correlations = pd.DataFrame(
    index=_ewmac_labels,
    columns=_ewmac_labels,
    data=[
        [1, np.nan, np.nan, np.nan, np.nan, np.nan],
        [0.9, 1, np.nan, np.nan, np.nan, np.nan],
        [0.6, 0.9, 1, np.nan, np.nan, np.nan],
        [0.35, 0.60, 0.90, 1, np.nan, np.nan],
        [0.2, 0.4, 0.65, 0.90, 1, np.nan],
        [0.15, 0.2, 0.45, 0.70, 0.90, 1],
    ],
)
