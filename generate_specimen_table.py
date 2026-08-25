"""
generate_specimen_table.py

Read a per-specimen CSV (or the global CSV filtered by specimen) and produce a pivot table
with rows = surgical conditions, columns = movements, cells = ROM (mean ± std if multiple runs).
The table order follows the example from Ariane's document.
"""

import pandas as pd
import os

# ========== CONFIGURATION ==========
# Path to the CSV file containing the data (can be global or per-specimen)
CSV_PATH = "ROM_3233_L.csv"   # <-- CHANGE to your per‑specimen file

# Output file name
OUTPUT_CSV = "ROM_Table_3233_L.csv"   # <-- will be saved as CSV

# Movements in the desired order (as in Ariane's example)
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

# Surgical conditions in the desired order (as in Ariane's example)
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

# ========== READ DATA ==========
df = pd.read_csv(CSV_PATH)

# Filter only rows with valid ROM (non‑NaN) if you want to exclude no‑criterion runs.
# However, leaving NaN will produce empty cells, which is acceptable.
# If you prefer to show something like "—", you can replace NaN later.

# Create a pivot table: index=Condition, columns=Movement, values=ROM_deg
# If multiple runs exist for the same condition+movement, we compute mean and std.
# We'll format as "mean ± std" or just "mean" if only one run.
pivot = df.pivot_table(
    index='Condition',
    columns='Movement',
    values='ROM_deg',
    aggfunc=lambda x: f"{x.mean():.2f} ± {x.std():.2f}" if len(x) > 1 else f"{x.mean():.2f}"
)

# Reorder rows and columns
pivot = pivot.reindex(index=CONDITION_ORDER, columns=MOVEMENT_ORDER)

# (Optional) Replace NaN with an empty string or a dash
pivot = pivot.fillna('')

# Save to CSV
pivot.to_csv(OUTPUT_CSV)
print(f"Table saved to {OUTPUT_CSV}")