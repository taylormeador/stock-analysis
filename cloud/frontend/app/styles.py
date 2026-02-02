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
        /* COMIC SANS EVERYTHING */
        * {
            font-family: 'Comic Sans MS', 'Comic Sans', cursive !important;
        }
        
        /* Main container styling */
        .main {
            padding: 2rem;
            background-color: #FFFFCC;
            background-image: 
                repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(255,255,255,.5) 10px, rgba(255,255,255,.5) 20px);
        }
        
        /* Custom header styling */
        .custom-header {
            font-size: 3rem;
            font-weight: 900;
            color: #FF00FF;
            margin-bottom: 1rem;
            border: 5px solid #FF00FF;
            padding: 1rem;
            background: linear-gradient(90deg, #FFFF00 0%, #00FFFF 50%, #FF00FF 100%);
            text-shadow: 3px 3px 0px #000000;
            text-align: center;
        }
        
        .custom-subheader {
            font-size: 2rem;
            font-weight: 800;
            color: #0000FF;
            margin-top: 2rem;
            margin-bottom: 1rem;
            border-left: 10px solid #FF6600;
            padding-left: 1rem;
            background-color: #CCFFCC;
        }
        
        /* Metric card styling - CHUNKY BORDERS */
        .metric-card {
            background: #FFCCFF;
            padding: 1.5rem;
            border: 5px solid #FF00FF;
            margin: 1rem 0;
            box-shadow: 5px 5px 0px #000000;
        }
        
        .metric-value {
            font-size: 2.5rem;
            font-weight: 900;
            color: #FF0000;
        }
        
        .metric-label {
            font-size: 1rem;
            color: #0000FF;
            text-transform: uppercase;
            font-weight: bold;
        }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background: #FFCCCC !important;
            border-right: 5px solid #FF0000 !important;
        }
        
        /* Button styling - BIG CHUNKY BUTTONS */
        .stButton button {
            background: linear-gradient(180deg, #FFFF00 0%, #FF9900 100%) !important;
            color: #000000 !important;
            border: 4px solid #000000 !important;
            border-radius: 0px !important;
            font-size: 1.2rem !important;
            font-weight: bold !important;
            padding: 0.75rem 2rem !important;
            box-shadow: 4px 4px 0px #000000 !important;
        }
        
        .stButton button:hover {
            background: linear-gradient(180deg, #FF9900 0%, #FFFF00 100%) !important;
            transform: translate(2px, 2px);
            box-shadow: 2px 2px 0px #000000 !important;
        }
        
        /* Metric styling */
        [data-testid="stMetricValue"] {
            color: #FF0000 !important;
            font-size: 2rem !important;
            font-weight: 900 !important;
        }
        
        [data-testid="stMetricLabel"] {
            color: #0000FF !important;
            font-weight: bold !important;
        }
        
        div[data-testid="stMetric"] {
            background-color: #CCFFFF !important;
            border: 4px solid #00CCFF !important;
            padding: 1rem !important;
            box-shadow: 4px 4px 0px #000000 !important;
        }
        
        /* Status badge styling - CHUNKY */
        .status-badge {
            display: inline-block;
            padding: 0.5rem 1rem;
            border: 3px solid #000000;
            font-size: 1rem;
            font-weight: 800;
            box-shadow: 3px 3px 0px #000000;
        }
        
        .status-success {
            background-color: #00FF00;
            color: #000000;
        }
        
        .status-warning {
            background-color: #FFFF00;
            color: #000000;
        }
        
        .status-error {
            background-color: #FF0000;
            color: #FFFFFF;
        }
        
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Card container - CHUNKY */
        .card {
            background-color: #FFFFCC;
            border: 5px solid #000000;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 5px 5px 0px #000000;
        }
        
        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background-color: #FFCCFF !important;
            border: 3px solid #FF00FF !important;
            border-radius: 0px !important;
            padding: 0.75rem 1.5rem !important;
            font-weight: bold !important;
            box-shadow: 3px 3px 0px #000000 !important;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #FF00FF !important;
            color: #FFFFFF !important;
        }
        
        /* Progress bar */
        .stProgress > div > div > div {
            background: linear-gradient(90deg, #FF0000 0%, #FFFF00 50%, #00FF00 100%) !important;
            height: 20px !important;
            border: 2px solid #000000 !important;
        }
        
        /* Info boxes */
        .stAlert {
            border: 4px solid #000000 !important;
            border-radius: 0px !important;
            box-shadow: 4px 4px 0px #000000 !important;
        }
        
        /* Dataframe tables - CHUNKY BORDERS */
        .stDataFrame {
            border: 5px solid #000000 !important;
            box-shadow: 5px 5px 0px #000000 !important;
        }
        
        /* Input fields */
        input, textarea, select {
            border: 3px solid #000000 !important;
            border-radius: 0px !important;
            font-weight: bold !important;
        }
        
        /* Expander */
        .streamlit-expanderHeader {
            background-color: #CCFFCC !important;
            border: 3px solid #00AA00 !important;
            border-radius: 0px !important;
            font-weight: bold !important;
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
            f"<p style='color: #0000FF; font-size: 1.2rem; font-weight: bold; text-align: center; background-color: #FFFF99; border: 3px solid #FF9900; padding: 0.5rem;'>{subtitle}</p>",
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

    # Apply alternating row colors - BRIGHT
    styled = styled.set_properties(
        **{
            "background-color": "#FFCCFF",
            "color": "#000000",
            "border": "3px solid #000000",
            "font-weight": "bold",
        }
    )

    # Header styling - CHUNKY
    styled = styled.set_table_styles(
        [
            {
                "selector": "thead th",
                "props": [
                    ("background-color", "#FF00FF"),
                    ("color", "#FFFFFF"),
                    ("font-weight", "900"),
                    ("text-align", "center"),
                    ("padding", "15px"),
                    ("border", "4px solid #000000"),
                    ("font-size", "16px"),
                ],
            },
            {
                "selector": "tbody td",
                "props": [
                    ("text-align", "center"),
                    ("padding", "12px"),
                    ("border", "3px solid #000000"),
                ],
            },
            {
                "selector": "tr:nth-child(even)",
                "props": [("background-color", "#CCFFFF")],
            },
            {
                "selector": "tr:nth-child(odd)",
                "props": [("background-color", "#FFFFCC")],
            },
            {
                "selector": "tr:hover",
                "props": [("background-color", "#FFFF99"), ("font-weight", "bold")],
            },
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
                    return (
                        "color: #00AA00; font-weight: 900; background-color: #CCFFCC;"
                    )
                elif val_float < 0:
                    return (
                        "color: #FF0000; font-weight: 900; background-color: #FFCCCC;"
                    )
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
        "info": ("#00CCFF", "#000000"),
        "success": ("#00FF00", "#000000"),
        "warning": ("#FFFF00", "#000000"),
        "error": ("#FF0000", "#FFFFFF"),
    }

    bg_color, text_color = box_colors.get(box_type, box_colors["info"])

    st.markdown(
        f"""
        <div style="
            background-color: {bg_color};
            border: 5px solid #000000;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 5px 5px 0px #000000;
        ">
            <h3 style="margin: 0 0 0.5rem 0; color: {text_color}; font-weight: 900;">{title}</h3>
            <p style="margin: 0; color: {text_color}; font-weight: bold;">{content}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
