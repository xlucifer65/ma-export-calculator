"""
app.py
------
Streamlit UI for the MA Export Cost Calculator.
This file handles inputs, triggers calculation, and displays results.
All business logic lives in utils/calculator.py.
"""

import streamlit as st
import pandas as pd
from utils.data_loader import load_rules, get_origins, get_destinations
from utils.calculator import calculate_costs

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="MA Export Cost Calculator",
    page_icon="✈️",
    layout="wide",
)

# ── Header ────────────────────────────────────────────────────────────────────

st.title("MA Export Cost Calculator")
st.caption("Internal use only · MA UK · MA France · MA Ireland · All costs in GBP")
st.divider()

# ── Load rules ────────────────────────────────────────────────────────────────

@st.cache_data
def get_rules():
    """Load and cache rules so the CSV is not re-read on every interaction."""
    return load_rules()

try:
    rules_df = get_rules()
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()
except ValueError as e:
    st.error(f"Invalid cost rules file: {e}")
    st.stop()
except Exception as e:
    st.error(f"Unexpected error loading cost rules: {e}")
    st.stop()

# ── Input section ─────────────────────────────────────────────────────────────

st.subheader("Shipment Details")

col1, col2 = st.columns(2)

with col1:
    origins = get_origins(rules_df)
    origin = st.selectbox(
        "Origin",
        options=origins,
        help="The country the shipment is being collected from.",
    )

    destinations = get_destinations(rules_df)
    destination = st.selectbox(
        "Destination",
        options=destinations,
        help="The country the shipment is being delivered to.",
    )

with col2:
    shipment_value = st.number_input(
        "Declared Shipment Value (£ GBP)",
        min_value=0.0,
        value=0.0,
        step=1000.0,
        format="%.2f",
        help="The full declared value of the shipment in GBP.",
    )

    shipment_weight = st.number_input(
        "Shipment Weight (kg)",
        min_value=0.0,
        value=0.0,
        step=0.5,
        format="%.2f",
        help="Total gross weight of the shipment in kilograms.",
    )

st.divider()

# ── Calculate button ──────────────────────────────────────────────────────────

calculate = st.button("Calculate Cost", type="primary", use_container_width=False)

# ── Results section ───────────────────────────────────────────────────────────

if calculate:

    # Input validation
    if shipment_value <= 0:
        st.warning("Please enter a valid shipment value greater than £0.")
        st.stop()

    if shipment_weight <= 0:
        st.warning("Please enter a valid shipment weight greater than 0 kg.")
        st.stop()

    # Run the calculation engine
    breakdown, total, warnings = calculate_costs(
        rules_df,
        origin,
        destination,
        shipment_value,
        shipment_weight,
    )

    # ── Warnings ──────────────────────────────────────────────────────────────

    if warnings:
        st.subheader("Warnings")
        for warning in warnings:
            # Missing required costs are shown as errors (red) — others as warnings (yellow)
            if warning.startswith("MISSING REQUIRED COST"):
                st.error(f"⚠️ {warning}")
            else:
                st.warning(f"⚠️ {warning}")

    # ── Cost breakdown table ──────────────────────────────────────────────────

    if breakdown:
        st.subheader(f"Cost Breakdown — {origin} → {destination}")

        df_display = pd.DataFrame(breakdown)

        # Format the cost column as currency strings for display
        df_display['Cost (GBP)'] = df_display['Cost (GBP)'].apply(lambda x: f"£{x:,.2f}")

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Cost Category':  st.column_config.TextColumn('Cost Category', width='medium'),
                'Type':           st.column_config.TextColumn('Calc Type',     width='small'),
                'Applied To':     st.column_config.TextColumn('Applied To',    width='medium'),
                'Rate':           st.column_config.TextColumn('Rate',          width='small'),
                'Cost (GBP)':     st.column_config.TextColumn('Cost (GBP)',    width='small'),
            },
        )

        # ── Total ─────────────────────────────────────────────────────────────

        st.divider()

        total_col, _ = st.columns([1, 2])
        with total_col:
            st.metric(
                label="Total Baseline Cost",
                value=f"£{total:,.2f}",
                help="Sum of all applicable cost components for this route. "
                     "This is a baseline estimate — final invoice may vary.",
            )

        # ── Route summary ─────────────────────────────────────────────────────

        with st.expander("Route Summary", expanded=False):
            st.write(f"**Origin:** {origin}")
            st.write(f"**Destination:** {destination}")
            st.write(f"**Declared Value:** £{shipment_value:,.2f}")
            st.write(f"**Weight:** {shipment_weight:.2f} kg")
            st.write(f"**Rules Applied:** {len(breakdown)}")

    else:
        st.error(
            "No costs could be calculated for this route. "
            "Please check that rules exist in the data file for this origin/destination."
        )
