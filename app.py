"""
app.py
------
Streamlit UI for the MA Export Cost Calculator.
This file handles inputs, triggers calculation, and displays results.
All business logic lives in utils/calculator.py.

Currency note:
  All rates in cost_rules.csv are stored in GBP.
  EUR conversion is applied at display time using the exchange rate entered by the user.
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
st.caption("Internal use only · MA UK · MA France · MA Ireland")
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

# ── Currency selector ─────────────────────────────────────────────────────────

curr_col, rate_col, _ = st.columns([1, 1, 2])

with curr_col:
    currency = st.selectbox(
        "Display Currency",
        options=["GBP (£)", "EUR (€)"],
        help="All rates are stored in GBP. EUR is converted at the rate you enter.",
    )

use_eur = currency == "EUR (€)"

with rate_col:
    fx_rate = st.number_input(
        "GBP → EUR Rate",
        min_value=0.01,
        value=1.17,
        step=0.01,
        format="%.4f",
        disabled=not use_eur,
        help="Enter today's GBP to EUR exchange rate. Only used when EUR is selected.",
    )

# Helper: format a GBP value into the selected display currency
def fmt_currency(gbp_amount: float) -> str:
    if use_eur:
        return f"€{gbp_amount * fx_rate:,.2f}"
    return f"£{gbp_amount:,.2f}"

symbol = "€" if use_eur else "£"

st.divider()

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
        f"Declared Shipment Value ({symbol})",
        min_value=0.0,
        value=0.0,
        step=1000.0,
        format="%.2f",
        help=f"The full declared value of the shipment in {symbol}.",
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

calculate = st.button("Calculate Cost", type="primary")

# ── Results section ───────────────────────────────────────────────────────────

if calculate:

    # Input validation
    if shipment_value <= 0:
        st.warning(f"Please enter a valid shipment value greater than {symbol}0.")
        st.stop()

    if shipment_weight <= 0:
        st.warning("Please enter a valid shipment weight greater than 0 kg.")
        st.stop()

    # Convert input value to GBP for the calculation engine (which always works in GBP)
    value_in_gbp = shipment_value / fx_rate if use_eur else shipment_value

    # Run the calculation engine (always returns GBP costs)
    breakdown, total_gbp, warnings = calculate_costs(
        rules_df,
        origin,
        destination,
        value_in_gbp,
        shipment_weight,
    )

    # ── Warnings ──────────────────────────────────────────────────────────────

    if warnings:
        st.subheader("Warnings")
        for warning in warnings:
            if warning.startswith("MISSING REQUIRED COST"):
                st.error(f"⚠️ {warning}")
            else:
                st.warning(f"⚠️ {warning}")

    # ── Cost breakdown table ──────────────────────────────────────────────────

    if breakdown:
        curr_label = "EUR (€)" if use_eur else "GBP (£)"
        st.subheader(f"Cost Breakdown — {origin} → {destination} · {curr_label}")

        df_display = pd.DataFrame(breakdown)

        # Rename and convert the cost column for display
        cost_col_label = f"Cost ({symbol})"
        df_display[cost_col_label] = df_display['Cost (GBP)'].apply(fmt_currency)
        df_display = df_display.drop(columns=['Cost (GBP)'])

        # Also update the "Applied To" column if EUR so declared value shows correctly
        if use_eur:
            df_display['Applied To'] = df_display['Applied To'].str.replace(
                r'£([\d,]+\.\d{2})',
                lambda m: f"€{float(m.group(1).replace(',','')) * fx_rate:,.2f}",
                regex=True,
            )

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Cost Category':  st.column_config.TextColumn('Cost Category', width='medium'),
                'Type':           st.column_config.TextColumn('Calc Type',     width='small'),
                'Applied To':     st.column_config.TextColumn('Applied To',    width='medium'),
                'Rate':           st.column_config.TextColumn('Rate',          width='small'),
                cost_col_label:   st.column_config.TextColumn(cost_col_label,  width='small'),
            },
        )

        # ── Total ─────────────────────────────────────────────────────────────

        st.divider()

        total_col, fx_info_col, _ = st.columns([1, 1, 1])

        with total_col:
            st.metric(
                label=f"Total Baseline Cost ({symbol})",
                value=fmt_currency(total_gbp),
                help="Sum of all applicable cost components. Baseline estimate only.",
            )

        # Show GBP equivalent when EUR is selected, so users can cross-reference
        if use_eur:
            with fx_info_col:
                st.metric(
                    label="Equivalent in GBP (£)",
                    value=f"£{total_gbp:,.2f}",
                    help=f"GBP base amount before conversion at rate {fx_rate:.4f}",
                )

        # ── Route summary ─────────────────────────────────────────────────────

        with st.expander("Route Summary", expanded=False):
            st.write(f"**Origin:** {origin}")
            st.write(f"**Destination:** {destination}")
            st.write(f"**Declared Value:** {fmt_currency(shipment_value if not use_eur else shipment_value)}")
            st.write(f"**Weight:** {shipment_weight:.2f} kg")
            st.write(f"**Display Currency:** {curr_label}")
            if use_eur:
                st.write(f"**Exchange Rate Used:** 1 GBP = {fx_rate:.4f} EUR")
            st.write(f"**Rules Applied:** {len(breakdown)}")

    else:
        st.error(
            "No costs could be calculated for this route. "
            "Please check that rules exist in the data file for this origin/destination."
        )
