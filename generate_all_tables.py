"""
generate_all_tables.py

Generate cleaned pivot tables for all specimens and a global average table.
Usage: python generate_all_tables.py
"""

import pandas as pd
import numpy as np
import os

# ========== CONFIGURATION ==========
# List of all specimens (according to Ariane's email)
SPECIMENS = [
    "3231_L",
    "3231_R",
    "3233_L",
    "3233_R",
    "3237_R",
    "3241_L",
    "3246_L",
    "3246_R"
]

# Movements in the desired order
MOVEMENT_ORDER = [
    "Flexion",
    "Flexion-Abduction",
    "Abduction",
    "Extension-Abduction",
    "Extension",
    "Extension-Adduction",
    "Adduction",
    "Flexion-Adduction"
]

# Surgical conditions in the desired order
CONDITION_ORDER = [
    "Neutral (0°)",
    "10° - Radial",
    "20° - Radial",
    "30° - Radial",
    "10° - Dorsal",
    "20° - Dorsal",
    "30° - Dorsal",
    "10° - Ulnar",
    "20° - Ulnar",
    "30° - Ulnar",
    "10° - Volar",
    "20° - Volar",
    "30° - Volar",
    "Native"
]

# ========== HELPER FUNCTIONS ==========
def format_rom(x):
    """
    Format a pandas Series of ROM values.
    If len(x) == 1: return "value"
    If len(x) > 1: return "mean ± std"
    """
    if len(x) == 0:
        return ""
    elif len(x) == 1:
        return f"{x.iloc[0]:.2f}"
    else:
        mean_val = x.mean()
        std_val = x.std()
        if pd.isna(std_val):
            return f"{mean_val:.2f}"
        else:
            return f"{mean_val:.2f} ± {std_val:.2f}"

def generate_specimen_table(csv_file, output_file):
    """
    Read a specimen CSV, create pivot table with cleaned formatting, and save.
    Returns the pivot DataFrame (or None if file not found).
    """
    if not os.path.exists(csv_file):
        print(f"  File {csv_file} not found – skipping.")
        return None
    df = pd.read_csv(csv_file)
    # Pivot: index=Condition, columns=Movement, values=ROM_deg
    pivot = df.pivot_table(
        index='Condition',
        columns='Movement',
        values='ROM_deg',
        aggfunc=format_rom
    )
    # Reorder rows and columns
    pivot = pivot.reindex(index=CONDITION_ORDER, columns=MOVEMENT_ORDER)
    # Fill missing cells with empty string
    pivot = pivot.fillna('')
    # Save
    pivot.to_csv(output_file)
    print(f"  Saved {output_file}")
    return pivot

def generate_average_table():
    """
    Compute average across specimens for each condition and movement.
    Returns a DataFrame with formatted "mean ± std" or just "mean" if only one value.
    """
    all_data = []  # list of dicts with keys (specimen, condition, movement, rom)
    for specimen in SPECIMENS:
        csv_file = f"ROM_{specimen}.csv"
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            for _, row in df.iterrows():
                cond = row['Condition']
                mov = row['Movement']
                rom = row['ROM_deg']
                if pd.notna(rom):
                    all_data.append({'specimen': specimen, 'condition': cond, 'movement': mov, 'rom': rom})
    # Convert to DataFrame
    full_df = pd.DataFrame(all_data)
    if full_df.empty:
        print("No data available for averaging.")
        return None
    # Compute mean and std per (condition, movement)
    mean_pivot = full_df.pivot_table(index='condition', columns='movement', values='rom', aggfunc='mean')
    std_pivot = full_df.pivot_table(index='condition', columns='movement', values='rom', aggfunc='std')
    # Build formatted table using lists to avoid dtype issues
    rows = []
    for cond in CONDITION_ORDER:
        row = []
        for mov in MOVEMENT_ORDER:
            if cond in mean_pivot.index and mov in mean_pivot.columns:
                mean_val = mean_pivot.loc[cond, mov]
                std_val = std_pivot.loc[cond, mov] if cond in std_pivot.index and mov in std_pivot.columns else np.nan
                if pd.isna(mean_val):
                    row.append("")
                elif pd.isna(std_val):
                    row.append(f"{mean_val:.2f}")
                else:
                    row.append(f"{mean_val:.2f} ± {std_val:.2f}")
            else:
                row.append("")
        rows.append(row)
    # Create DataFrame with object dtype
    formatted = pd.DataFrame(rows, index=CONDITION_ORDER, columns=MOVEMENT_ORDER, dtype=object)
    return formatted

# ========== MAIN ==========
if __name__ == "__main__":
    print("Generating per‑specimen tables...")
    specimen_pivots = []
    for spec in SPECIMENS:
        print(f"\nProcessing {spec}...")
        csv_file = f"ROM_{spec}.csv"
        out_file = f"ROM_Table_{spec}.csv"
        pivot = generate_specimen_table(csv_file, out_file)
        if pivot is not None:
            specimen_pivots.append(pivot)

    print("\nGenerating average across specimens table...")
    avg_table = generate_average_table()
    if avg_table is not None:
        avg_table.to_csv("ROM_Table_Average.csv")
        print("  Saved ROM_Table_Average.csv")
    else:
        print("  No average table generated.")

    print("\nDone.")