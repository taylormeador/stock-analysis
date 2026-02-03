"""
Minimal styling for the Streamlit dashboard.
Most styling comes from config.toml - this just adds terminal aesthetic touches.
"""

import streamlit as st
import pandas as pd
from dataclasses import dataclass


@dataclass
class Colors:
    # Primary colors
    bright_green: str = "#00FF41"  # Primary green (Matrix/terminal green)
    blue: str = "#58A6FF"  # Primary blue (links, accents)
    orange: str = "#FF9900"  # Orange/gold (warnings, negatives, yesterday data)

    # Backgrounds
    dark_bg: str = "#0d1117"  # Main background
    secondary_bg: str = "#161b22"  # Secondary/card background

    # Text
    text_gray: str = "#C9D1D9"  # Main text color

    # Alternative colors (for future use)
    alt_green: str = "#00C932"  # Alternative bright green
    alt_blue: str = "#4B8BCF"  # Alternative blue


colors = Colors()


def apply_custom_css():
    """Apply minimal custom CSS - let config.toml handle colors."""
    st.markdown(
        f"""
        <style>
        /* Import Material Icons */
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
        
        /* Ensure Material Icons work */
        .material-symbols-outlined {{
            font-family: 'Material Symbols Outlined' !important;
        }}
        
        /* Terminal scan lines effect */
        .main {{
            background-image: 
                repeating-linear-gradient(
                    0deg,
                    rgba(0, 255, 65, 0.02),
                    rgba(0, 255, 65, 0.02) 1px,
                    transparent 1px,
                    transparent 2px
                );
        }}
        
        /* Navigation alignment */
        [data-testid="stSidebarNav"] a {{
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 0.75rem 1rem !important;
            gap: 0.75rem !important;
        }}
        
        [data-testid="stSidebarNav"] svg {{
            width: 20px !important;
            height: 20px !important;
            flex-shrink: 0 !important;
        }}
        
        /* Tab styling - override Streamlit defaults */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.5rem;
        }}
        
        .stTabs [data-baseweb="tab"] {{
            color: {colors.text_gray} !important;
            background-color: transparent !important;
            border: 1px solid rgba(0, 255, 65, 0.3) !important;
            border-radius: 0px !important;
            padding: 0.5rem 1rem !important;
        }}
        
        .stTabs [data-baseweb="tab"]:hover {{
            background-color: rgba(0, 255, 65, 0.1) !important;
            color: {colors.bright_green} !important;
        }}
        
        .stTabs [aria-selected="true"] {{
            background-color: rgba(0, 255, 65, 0.15) !important;
            border-color: {colors.bright_green} !important;
            color: {colors.bright_green} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_large_number(num: float) -> str:
    """Format large numbers with K/M/B suffixes."""
    if abs(num) >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    elif abs(num) >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif abs(num) >= 1_000:
        return f"{num / 1_000:.1f}K"
    else:
        return f"{num:.0f}"


def format_percentage(num: float, include_sign: bool = True) -> str:
    """Format percentage values."""
    if include_sign and num > 0:
        return f"+{num:.1f}%"
    return f"{num:.1f}%"
