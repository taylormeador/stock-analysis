"""
Consistent styling and theming for the Streamlit dashboard.
"""

import streamlit as st
import pandas as pd


def apply_custom_css():
    """Apply custom CSS for consistent styling across the app."""
    st.markdown(
        """
        <style>
        /* Main container styling */
        .main {
            padding: 2rem;
        }
        
        /* Custom header styling */
        .custom-header {
            font-size: 2.5rem;
            font-weight: 700;
            color: #00d4aa;
            margin-bottom: 0.5rem;
            border-bottom: 3px solid #00d4aa;
            padding-bottom: 0.5rem;
        }
        
        .custom-subheader {
            font-size: 1.5rem;
            font-weight: 600;
            color: #fafafa;
            margin-top: 2rem;
            margin-bottom: 1rem;
        }
        
        /* Metric card styling */
        .metric-card {
            background: linear-gradient(135deg, #1a1d29 0%, #252838 100%);
            padding: 1.5rem;
            border-radius: 10px;
            border-left: 4px solid #00d4aa;
            margin: 1rem 0;
        }
        
        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            color: #00d4aa;
        }
        
        .metric-label {
            font-size: 0.9rem;
            color: #a0a0a0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        /* Table styling */
        .styled-table {
            border-collapse: collapse;
            margin: 25px 0;
            font-size: 0.9em;
            min-width: 400px;
            border-radius: 8px 8px 0 0;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
        }
        
        .styled-table thead tr {
            background-color: #00d4aa;
            color: #0e1117;
            text-align: left;
            font-weight: bold;
        }
        
        .styled-table th,
        .styled-table td {
            padding: 12px 15px;
        }
        
        .styled-table tbody tr {
            border-bottom: 1px solid #2a2e3a;
        }
        
        .styled-table tbody tr:nth-of-type(even) {
            background-color: #1a1d29;
        }
        
        .styled-table tbody tr:last-of-type {
            border-bottom: 2px solid #00d4aa;
        }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1a1d29 0%, #0e1117 100%);
        }
        
        /* Remove extra padding from dataframes */
        .stDataFrame {
            border: none !important;
        }
        
        /* Status badge styling */
        .status-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        
        .status-success {
            background-color: #00d4aa;
            color: #0e1117;
        }
        
        .status-warning {
            background-color: #ffa726;
            color: #0e1117;
        }
        
        .status-error {
            background-color: #ef5350;
            color: #fafafa;
        }
        
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Card container */
        .card {
            background-color: #1a1d29;
            border-radius: 10px;
            padding: 1.5rem;
            margin: 1rem 0;
            border: 1px solid #2a2e3a;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def create_header(title: str, subtitle: str = ""):
    """Create a consistent page header."""
    st.markdown(f'<div class="custom-header">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(
            f"<p style='color: #a0a0a0; font-size: 1.1rem;'>{subtitle}</p>",
            unsafe_allow_html=True,
        )
    st.markdown("<br>", unsafe_allow_html=True)


def create_subheader(text: str):
    """Create a consistent subheader."""
    st.markdown(f'<div class="custom-subheader">{text}</div>', unsafe_allow_html=True)


def style_dataframe(df: pd.DataFrame, highlight_col: str = None) -> pd.DataFrame:
    """
    Apply consistent styling to a pandas DataFrame for display.

    Args:
        df: DataFrame to style
        highlight_col: Column name to apply special highlighting (e.g., for percent changes)

    Returns:
        Styled DataFrame
    """
    styled = df.style

    # Apply alternating row colors
    styled = styled.set_properties(
        **{
            "background-color": "#1a1d29",
            "color": "#fafafa",
            "border": "1px solid #2a2e3a",
        }
    )

    # Header styling
    styled = styled.set_table_styles(
        [
            {
                "selector": "thead th",
                "props": [
                    ("background-color", "#00d4aa"),
                    ("color", "#0e1117"),
                    ("font-weight", "bold"),
                    ("text-align", "center"),
                    ("padding", "12px"),
                ],
            },
            {
                "selector": "tbody td",
                "props": [("text-align", "center"), ("padding", "10px")],
            },
            {"selector": "tr:hover", "props": [("background-color", "#252838")]},
        ]
    )

    # Highlight specific column if provided
    if highlight_col and highlight_col in df.columns:

        def highlight_value(val):
            if pd.isna(val):
                return ""
            try:
                val_float = float(val)
                if val_float > 0:
                    return "color: #00d4aa; font-weight: bold"
                elif val_float < 0:
                    return "color: #ef5350; font-weight: bold"
            except (ValueError, TypeError):
                pass
            return ""

        styled = styled.applymap(highlight_value, subset=[highlight_col])

    # Format numeric columns
    for col in df.select_dtypes(include=["float64", "float32"]).columns:
        styled = styled.format({col: "{:.2f}"})

    return styled


def create_metric_card(
    label: str, value: str, delta: str = None, delta_color: str = "normal"
):
    """
    Create a styled metric card.

    Args:
        label: Metric label
        value: Metric value
        delta: Optional delta value
        delta_color: Color for delta ("normal", "inverse", or "off")
    """
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def format_large_number(num: float) -> str:
    """Format large numbers with K, M, B suffixes."""
    if abs(num) >= 1_000_000_000:
        return f"{num / 1_000_000_000:.2f}B"
    elif abs(num) >= 1_000_000:
        return f"{num / 1_000_000:.2f}M"
    elif abs(num) >= 1_000:
        return f"{num / 1_000:.2f}K"
    return f"{num:.2f}"


def format_percentage(num: float, include_sign: bool = True) -> str:
    """Format a number as a percentage."""
    sign = "+" if num > 0 and include_sign else ""
    return f"{sign}{num:.2f}%"


def create_status_badge(status: str) -> str:
    """
    Create a colored status badge.

    Args:
        status: One of "success", "warning", "error"

    Returns:
        HTML for the status badge
    """
    status_map = {
        "success": ("✓ Active", "status-success"),
        "warning": ("⚠ Degraded", "status-warning"),
        "error": ("✗ Error", "status-error"),
    }

    text, css_class = status_map.get(status, ("Unknown", "status-warning"))
    return f'<span class="status-badge {css_class}">{text}</span>'


def create_info_box(title: str, content: str, box_type: str = "info"):
    """
    Create an information box.

    Args:
        title: Box title
        content: Box content
        box_type: One of "info", "success", "warning", "error"
    """
    box_colors = {
        "info": "#00d4aa",
        "success": "#00d4aa",
        "warning": "#ffa726",
        "error": "#ef5350",
    }

    color = box_colors.get(box_type, box_colors["info"])

    st.markdown(
        f"""
        <div style="
            background-color: #1a1d29;
            border-left: 4px solid {color};
            padding: 1rem;
            border-radius: 5px;
            margin: 1rem 0;
        ">
            <h4 style="margin: 0 0 0.5rem 0; color: {color};">{title}</h4>
            <p style="margin: 0; color: #fafafa;">{content}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
