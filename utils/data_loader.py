"""
data_loader.py
--------------
Responsible for loading and filtering cost rules from the CSV file.
This module does NOT do any cost calculations — it only handles data access.
"""

import os
import pandas as pd
from datetime import date


# Path to the CSV, relative to this file's location
RULES_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'cost_rules.csv')

# These categories must be present for a route to be considered complete
REQUIRED_CATEGORIES = [
    'Freight',
    'Liability',
    'War Risk',
    'Airline Handling',
    'Airport Security',
    'Customs',
]


def load_rules() -> pd.DataFrame:
    """
    Load cost rules from CSV, filter to only active rules
    that are valid as of today's date.

    Returns:
        pd.DataFrame: Filtered rules ready for the calculator.

    Raises:
        FileNotFoundError: If the CSV does not exist at the expected path.
        ValueError: If required columns are missing from the CSV.
    """
    if not os.path.exists(RULES_PATH):
        raise FileNotFoundError(
            f"Cost rules file not found at: {RULES_PATH}\n"
            "Please ensure data/cost_rules.csv exists."
        )

    df = pd.read_csv(RULES_PATH)

    # Validate that expected columns are present
    required_cols = {
        'rule_id', 'origin', 'destination', 'cost_category',
        'calculation_type', 'rate', 'minimum_charge', 'currency',
        'active_flag', 'effective_from',
    }
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValueError(f"CSV is missing required columns: {missing_cols}")

    # Keep only active rules
    df = df[df['active_flag'].astype(str).str.upper() == 'TRUE'].copy()

    # Filter by effective_from date (rule must have started)
    today = date.today().isoformat()
    df['effective_from'] = df['effective_from'].astype(str)
    df = df[df['effective_from'] <= today]

    # Filter by effective_to date (blank means no end date = still active)
    if 'effective_to' in df.columns:
        df['effective_to'] = df['effective_to'].astype(str).replace('nan', '')
        df = df[(df['effective_to'] == '') | (df['effective_to'] >= today)]

    # Ensure numeric columns are the right type
    df['rate'] = pd.to_numeric(df['rate'], errors='coerce').fillna(0.0)
    df['minimum_charge'] = pd.to_numeric(df['minimum_charge'], errors='coerce')

    df = df.reset_index(drop=True)
    return df


def get_origins(rules_df: pd.DataFrame) -> list:
    """Return sorted list of available origins from the loaded rules."""
    return sorted(rules_df['origin'].unique().tolist())


def get_destinations(rules_df: pd.DataFrame) -> list:
    """
    Return sorted list of available destinations.
    Excludes the wildcard '*' — that is an internal routing concept only.
    """
    all_destinations = rules_df['destination'].unique().tolist()
    return sorted([d for d in all_destinations if d != '*'])
