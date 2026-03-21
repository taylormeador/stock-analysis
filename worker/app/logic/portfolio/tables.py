import pandas as pd
import numpy as np

# FDM - Forecast Diversification Multiplier - Scales up individual subsystem positions to hit vol target based on correlation across all subsystems

# Table 18: diversification multiplier
# Carver recommends capping this at 2.5
forecast_diversification_multipliers = pd.DataFrame(
    # number valued columns are the average correlation between assets
    columns=["num_assets", 0.0, 0.25, 0.5, 0.75, 1.0],
    data=[
        [2, 1.41, 1.27, 1.15, 1.10, 1.0],
        [3, 1.73, 1.41, 1.22, 1.12, 1.0],
        [4, 2.0, 1.51, 1.27, 1.10, 1.0],
        [5, 2.2, 1.58, 1.29, 1.15, 1.0],
        [10, 3.2, 1.75, 1.35, 1.17, 1.0],
        [15, 3.9, 1.83, 1.37, 1.17, 1.0],
        [20, 4.5, 1.86, 1.38, 1.18, 1.0],
        [50, 7.1, 1.94, 1.40, 1.19, 1.0],
    ],
)

# Table 50: Correlations of instrument returns across super-asset classes
super_asset_correlations = pd.DataFrame(
    columns=["asset", "bonds", "equities", "fx", "commodities", "vol"],
    data=[
        ["rates", 1, np.nan, np.nan, np.nan, np.nan],
        ["equities", 0.1, 1, np.nan, np.nan, np.nan],
        ["fx", 0.1, 0.1, 1, np.nan, np.nan],
        ["commodities", 0.1, 0.1, 0.25, 1, np.nan],
        ["vol", 0.1, 0.6, 0.2, 0.1, 1],
    ],
)

# Table 51: Correlation of instrument returns, across asset classes
asset_correlations = pd.DataFrame(
    columns=["asset", "bonds", "STIR", "agricultural", "metal", "energy"],
    data=[
        ["bonds", 1, 0.5, np.nan, np.nan, np.nan],
        ["STIR", 0.5, 1, np.nan, np.nan, np.nan],
        ["agricultural", np.nan, np.nan, 1, np.nan, np.nan],
        ["metal", np.nan, np.nan, 0.2, 1, np.nan],
        ["energy", np.nan, np.nan, 0.25, 0.35, 1],
    ],
)

# Table 52: Correlation of instrument returns, by sub asset class, within commodity asset classes
sub_asset_correlations = pd.DataFrame(
    columns=[
        "asset",
        "grains",
        "softs",
        "livestock",
        "oil",
        "gas",
        "precious_metals",
        "base",
    ],
    data=[
        ["grains", 1, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan],
        ["softs", 0.4, 1, np.nan, np.nan, np.nan, np.nan, np.nan],
        ["livestock", 0.25, 0.15, 1, np.nan, np.nan, np.nan, np.nan],
        ["oil", np.nan, np.nan, np.nan, 1, np.nan, np.nan, np.nan],
        ["gas", np.nan, np.nan, np.nan, 0.25, 1, np.nan, np.nan],
        ["precious_metals", np.nan, np.nan, np.nan, np.nan, np.nan, 1, np.nan],
        ["base_metals", np.nan, np.nan, np.nan, np.nan, np.nan, 0.5, 1],
    ],
)

# Table 53: Correlations of instrument returns for regions within financial asset classes
# All correlations are for emerging and developed markets
asset_class_region_correlations = pd.DataFrame(
    columns=["asset", "correlation"],
    data=[
        ["bonds", 0.35],
        ["STIR", 0.35],
        ["equities", 0.50],
        ["col", 0.50],
        ["fx", 0.15],
    ],
)

# Table 54: Correlation of instrument returns, within regions and sub asset classes
sub_asset_class_region_correlations = pd.DataFrame(
    columns=["asset", "correlation"],
    data=[
        ["bonds", 0.35],  # same region, different countries
        ["equities_country", 0.35],  # same region, different countries
        ["fx", 0.50],  # same region, different rates against USD
        ["vol", 0.50],  # same region, different countries
        ["commodities", 0.15],  # same sub asset class, different products
        ["equities_industry", 0.15],  # same country, different industry
        ["equities_firm", 0.15],  # same industry, different firms
    ],
)

# Table 55: Correlation of instrument returns, for bonds or bond futures of different duration in same country
bond_correlations = pd.DataFrame(
    columns=["asset", "2_year", "5_year", "10_year", "20_year", "30_year"],
    data=[
        ["2_year", 1, np.nan, np.nan, np.nan, np.nan],
        ["5_year", 0.8, 1, np.nan, np.nan, np.nan],
        ["10_year", 0.65, 0.85, 1, np.nan, np.nan],
        ["20_year", 0.5, 0.80, 0.85, 1, np.nan],
        ["30_year", 0.5, 0.75, 0.80, 0.90, 1],
    ],
)

# IDM - Instrument Diversification Multiplier - Scales up the combined forecast for a specific instrument based on correlation of rules/variations within the subsystem

# Table 56: Correlation of trading rule returns within an instrument
rule_correlations = pd.DataFrame(
    columns=["type", "correlation"],
    data=[
        ["different_styles", 0.25],  # e.g. momentum and carry
        ["different_rules", 0.5],  # e.g. EWMAC and other trend following rules
    ],
)

# Table 57: Correlation of trading rule returns within an instrument, variations on EWMAC rule
ewmac_correlations = pd.DataFrame(
    columns=[
        "variation",
        "ewmac_2_8",
        "ewmac_4_16",
        "ewmac_8_32",
        "ewmac_16_64",
        "ewmac_32_128",
        "ewmac_64_256",
    ],
    data=[
        ["ewmac_2_8", 1, np.nan, np.nan, np.nan, np.nan, np.nan],
        ["ewmac_4_16", 0.9, 1, np.nan, np.nan, np.nan, np.nan],
        ["ewmac_8_32", 0.6, 0.9, 1, np.nan, np.nan, np.nan],
        ["ewmac_16_64", 0.35, 0.60, 0.90, 1, np.nan, np.nan],
        ["ewmac_32_128", 0.2, 0.4, 0.65, 0.90, 1, np.nan],
        ["ewmac_64_256", 0.15, 0.2, 0.45, 0.70, 0.90, 1],
    ],
)

# TODO implement carry
carry_correlations = pd.DataFrame(
    columns=[
        "variation",
        "ewmac_2_8",
        "ewmac_4_16",
        "ewmac_8_32",
        "ewmac_16_64",
        "ewmac_32_128",
        "ewmac_64_256",
    ],
    data=[
        ["ewmac_2_8", 1, np.nan, np.nan, np.nan, np.nan, np.nan],
        ["ewmac_4_16", 0.9, 1, np.nan, np.nan, np.nan, np.nan],
        ["ewmac_8_32", 0.6, 0.9, 1, np.nan, np.nan, np.nan],
        ["ewmac_16_64", 0.35, 0.60, 0.90, 1, np.nan, np.nan],
        ["ewmac_32_128", 0.2, 0.4, 0.65, 0.90, 1, np.nan],
        ["ewmac_64_256", 0.15, 0.2, 0.45, 0.70, 0.90, 1],
    ],
)
