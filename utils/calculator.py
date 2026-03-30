"""
calculator.py
-------------
Core calculation engine for the MA export cost calculator.
This module does NOT touch the UI or load files — it only applies business logic.

Rule priority:
  - Specific destination rules (origin + destination match) override
    wildcard rules (origin + destination = '*') for the same cost category.
"""

import pandas as pd
from utils.data_loader import REQUIRED_CATEGORIES


def get_matching_rules(rules_df: pd.DataFrame, origin: str, destination: str) -> pd.DataFrame:
    """
    Find all applicable rules for a given origin and destination.

    Priority logic:
      1. If a specific rule exists for (origin, destination) in a category → use it.
      2. If only a wildcard rule exists for (origin, *) in a category → use it.
      3. If both exist for the same category → specific wins, wildcard is dropped.

    Args:
        rules_df: Full filtered rules DataFrame from data_loader.
        origin: Selected origin (e.g. 'UK').
        destination: Selected destination (e.g. 'USA').

    Returns:
        pd.DataFrame: Deduplicated rules to apply for this route.
    """
    # Filter to this origin only
    origin_rules = rules_df[rules_df['origin'] == origin]

    # Split into specific-destination rules and wildcard rules
    specific = origin_rules[origin_rules['destination'] == destination].copy()
    wildcard = origin_rules[origin_rules['destination'] == '*'].copy()

    # Categories already covered by a specific rule
    specific_categories = set(specific['cost_category'].tolist())

    # Only keep wildcard rules for categories NOT covered by a specific rule
    wildcard_filtered = wildcard[~wildcard['cost_category'].isin(specific_categories)]

    # Combine: specific rules take precedence
    matched = pd.concat([specific, wildcard_filtered], ignore_index=True)
    return matched


def format_rate_display(calculation_type: str, rate: float) -> str:
    """Return a human-readable rate string for the breakdown table."""
    if calculation_type == 'percentage':
        return f"{rate:.2f}%"
    elif calculation_type == 'per_kg':
        return f"£{rate:.2f} / kg"
    elif calculation_type == 'fixed':
        return f"£{rate:.2f} flat"
    return str(rate)


def format_base_display(calculation_type: str, shipment_value: float, shipment_weight: float) -> str:
    """Return a human-readable description of what value the rate was applied to."""
    if calculation_type == 'percentage':
        return f"£{shipment_value:,.2f} (declared value)"
    elif calculation_type == 'per_kg':
        return f"{shipment_weight:.2f} kg"
    elif calculation_type == 'fixed':
        return "—"
    return "—"


def calculate_line_item(rule: pd.Series, shipment_value: float, shipment_weight: float) -> float:
    """
    Calculate the cost for a single rule row.

    Applies:
      - percentage  → shipment_value × (rate / 100)
      - per_kg      → shipment_weight × rate
      - fixed       → rate (flat charge)

    Then enforces the minimum_charge if one is defined.

    Args:
        rule: A single row from the matched rules DataFrame.
        shipment_value: Declared value in GBP.
        shipment_weight: Weight in kg.

    Returns:
        float: Final cost for this line item, rounded to 2 decimal places.
    """
    calc_type = rule['calculation_type']
    rate = float(rule['rate'])

    if calc_type == 'percentage':
        cost = shipment_value * (rate / 100)
    elif calc_type == 'per_kg':
        cost = shipment_weight * rate
    elif calc_type == 'fixed':
        cost = rate
    else:
        # Unknown calculation type — skip with zero (logged as warning elsewhere)
        cost = 0.0

    # Apply minimum charge if defined
    min_charge = rule['minimum_charge']
    if pd.notna(min_charge) and float(min_charge) > 0:
        cost = max(cost, float(min_charge))

    return round(cost, 2)


def calculate_costs(
    rules_df: pd.DataFrame,
    origin: str,
    destination: str,
    shipment_value: float,
    shipment_weight: float,
) -> tuple[list[dict], float, list[str]]:
    """
    Main entry point for the calculation engine.

    Steps:
      1. Find matching rules for the route.
      2. Calculate each line item.
      3. Check for missing required cost categories.
      4. Return breakdown, total, and any warnings.

    Args:
        rules_df: Loaded and filtered rules DataFrame.
        origin: Selected origin (e.g. 'UK').
        destination: Selected destination (e.g. 'UAE').
        shipment_value: Declared shipment value in GBP.
        shipment_weight: Shipment weight in kg.

    Returns:
        breakdown (list[dict]): Line-by-line cost items.
        total (float): Sum of all line item costs.
        warnings (list[str]): Any issues found (missing rules, unknown types, etc.)
    """
    breakdown = []
    warnings = []

    matched = get_matching_rules(rules_df, origin, destination)

    # No rules found at all for this route
    if matched.empty:
        warnings.append(
            f"No cost rules found for route: {origin} → {destination}. "
            "Please contact the pricing team."
        )
        return breakdown, 0.0, warnings

    # Calculate each matched rule
    for _, rule in matched.iterrows():
        calc_type = rule['calculation_type']

        # Warn about unrecognised calculation types but continue
        if calc_type not in ('percentage', 'per_kg', 'fixed'):
            warnings.append(
                f"Unknown calculation type '{calc_type}' for rule {rule['rule_id']} "
                f"({rule['cost_category']}) — skipped."
            )
            continue

        cost = calculate_line_item(rule, shipment_value, shipment_weight)

        breakdown.append({
            'Cost Category':    rule['cost_category'],
            'Type':             calc_type,
            'Applied To':       format_base_display(calc_type, shipment_value, shipment_weight),
            'Rate':             format_rate_display(calc_type, float(rule['rate'])),
            'Cost (GBP)':       cost,
        })

    # Check for missing required categories and warn clearly
    calculated_categories = {item['Cost Category'] for item in breakdown}
    for required_cat in REQUIRED_CATEGORIES:
        if required_cat not in calculated_categories:
            warnings.append(
                f"MISSING REQUIRED COST: '{required_cat}' — no rule found for "
                f"{origin} → {destination}. Total may be incomplete."
            )

    total = round(sum(item['Cost (GBP)'] for item in breakdown), 2)
    return breakdown, total, warnings
