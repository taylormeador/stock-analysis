"""
Minimal styling for the Streamlit dashboard.
Most styling comes from config.toml - this just adds terminal aesthetic touches.
"""

import streamlit as st
import pandas as pd


def apply_custom_css():
    """Apply minimal custom CSS - let config.toml handle colors."""
    st.markdown(
        """
        <style>
        /* Import Material Icons */
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
        
        /* Ensure Material Icons work */
        .material-symbols-outlined {
            font-family: 'Material Symbols Outlined' !important;
        }
        
        /* Terminal scan lines effect */
        .main {
            background-image: 
                repeating-linear-gradient(
                    0deg,
                    rgba(0, 255, 65, 0.02),
                    rgba(0, 255, 65, 0.02) 1px,
                    transparent 1px,
                    transparent 2px
                );
        }
        
        /* Navigation alignment */
        [data-testid="stSidebarNav"] a {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 0.75rem 1rem !important;
            gap: 0.75rem !important;
        }
        
        [data-testid="stSidebarNav"] svg {
            width: 20px !important;
            height: 20px !important;
            flex-shrink: 0 !important;
        }
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
