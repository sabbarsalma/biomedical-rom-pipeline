"""
build_adduction_table.py

Process all processed TDMS files for adduction (ADD_dislocation) in the given specimen folders.
For each file, extract time, ulnar rotation angle, three translations, three torques,
and determine the ROM limit using the four hierarchical criteria.
For torque drops (criterion 2), we use a rate threshold (Nm/s) if time is available.
Output a CSV table with columns: Specimen, Condition, ROM_ulnar_deg, Critere, File.
"""

import os
import numpy as np
import pandas as pd
from nptdms import TdmsFile

# ========== CONFIGURATION ==========
# List of specimen folders (full paths)
SPECIMEN_FOLDERS = [
    "/path/to/All_Specimens/3231_L",
    "/path/to/All_Specimens/3241_L"
]

MOVEMENT_CODE = "ADD_dislocation"      # adduction movement
FILE_TYPE = "processed"                # only processed files

# TDMS group and channel names (based on your exploration)
GROUP_KINEMATICS = "Kinematics.JCS.Actual"
GROUP_LOAD = "State.JCS Load"

CH_ULNAR = "Ulnar Rotation"
CH_VOLAR = "Volar (R) Translation"
CH_PROXIMAL = "Proximal (R) Translation"
CH_RADIAL_TRANS = "Radial (R)Translation"
CH_RADIAL_TORQUE = "JCS Load Radial Rotation Torque"
CH_SUPINATION_TORQUE = "JCS Load Supination Torque"
CH_EXTENSION_TORQUE = "JCS Load Extension Torque"

# Drop thresholds 
DROP_TRANSLATION = -0.2      # mm drop between consecutive samples
DROP_TORQUE = -0.02           # Nm drop between consecutive samples

# ========== MAPPING: condition code -> display name ==========
CONDITION_MAP = {
    "BP_0": "Neutral (0°)",
    "BP10_Radial": "10° - Radial",
    "BP20_Radial": "20° - Radial",
    "BP30_Radial": "30° - Radial",
    "BP10_Dorsal": "10° - Dorsal",
    "BP20_Dorsal": "20° - Dorsal",
    "BP30_Dorsal": "30° - Dorsal",
    "BP10_Ulnar": "10° - Ulnar",
    "BP20_Ulnar": "20° - Ulnar",
    "BP30_Ulnar": "30° - Ulnar",
    "BP10_Volar": "10° - Volar",
    "BP20_Volar": "20° - Volar",
    "BP30_Volar": "30° - Volar",
    "Native": "Native"
}

def extract_condition_code(filename):
    """Return the condition code (e.g., 'BP10_Ulnar') found in filename."""
    for code in CONDITION_MAP:
        if code in filename:
            return code
    return "Unknown"

def extract_specimen_from_path(filepath):
    """
    Extract the specimen folder name (e.g., '3231_L') from the full path.
    Assumes structure: .../SpecimenFolder/ExperimentRun/Data/filename.tdms
    """
    try:
        # Go up three levels: filename -> Data -> ExperimentRun -> SpecimenFolder
        specimen_folder = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(filepath))))
        return specimen_folder
    except:
        return "Unknown"

def resultant_torque(radial, supination, extension):
    """Compute resultant torque from three components."""
    return np.sqrt(radial**2 + supination**2 + extension**2)

# ========== COLLECT ALL RELEVANT FILES ==========
target_files = []
for folder in SPECIMEN_FOLDERS:
    for root, dirs, files in os.walk(folder):
        for f in files:
            if (MOVEMENT_CODE in f) and (FILE_TYPE in f) and f.endswith('.tdms'):
                target_files.append(os.path.join(root, f))

print(f"Found {len(target_files)} files.\n")

results = []

# ========== PROCESS EACH FILE ==========
for filepath in target_files:
    filename = os.path.basename(filepath)
    print(f"Processing: {filename}")

    specimen = extract_specimen_from_path(filepath)
    code = extract_condition_code(filename)
    condition = CONDITION_MAP.get(code, code)
    print(f"  Specimen: {specimen} | Condition: {condition}")

    try:
        with TdmsFile.open(filepath) as tdms:
            grp_kin = tdms[GROUP_KINEMATICS]
            grp_load = tdms[GROUP_LOAD]

            # Read data as numpy arrays
            ulnar = np.array(grp_kin[CH_ULNAR].read_data())
            volar = np.array(grp_kin[CH_VOLAR].read_data())
            proximal = np.array(grp_kin[CH_PROXIMAL].read_data())
            radial_trans = np.array(grp_kin[CH_RADIAL_TRANS].read_data())
            radial_torque = np.array(grp_load[CH_RADIAL_TORQUE].read_data())
            supination_torque = np.array(grp_load[CH_SUPINATION_TORQUE].read_data())
            extension_torque = np.array(grp_load[CH_EXTENSION_TORQUE].read_data())

            # Resultant torque
            torque_res = resultant_torque(radial_torque, supination_torque, extension_torque)

            # Initial translation values (for criterion 4)
            n_init = 10
            volar_init = np.mean(volar[:n_init])
            proximal_init = np.mean(proximal[:n_init])
            radial_trans_init = np.mean(radial_trans[:n_init])

            # Search for first criterion (priority order 1→4)
            criterion = None
            angle_limit = None

            for i in range(1, len(ulnar)):
                # Criterion 1: sudden translation drop
                if (volar[i] - volar[i-1] < DROP_TRANSLATION or
                    proximal[i] - proximal[i-1] < DROP_TRANSLATION or
                    radial_trans[i] - radial_trans[i-1] < DROP_TRANSLATION):
                    criterion = 1
                    angle_limit = ulnar[i]
                    print(f"    Criterion 1 at i={i}, angle={angle_limit:.2f}°")
                    break

                # Criterion 2: sudden torque drop
                if (radial_torque[i] - radial_torque[i-1] < DROP_TORQUE or
                    supination_torque[i] - supination_torque[i-1] < DROP_TORQUE or
                    extension_torque[i] - extension_torque[i-1] < DROP_TORQUE):
                    criterion = 2
                    angle_limit = ulnar[i]
                    print(f"    Criterion 2 at i={i}, angle={angle_limit:.2f}°")
                    break

                # Criterion 3: resultant torque ≥ 1 Nm
                if torque_res[i] >= 1.0:
                    criterion = 3
                    angle_limit = ulnar[i]
                    print(f"    Criterion 3 at i={i}, angle={angle_limit:.2f}°")
                    break

                # Criterion 4: translation > 4 mm from start
                if (abs(volar[i] - volar_init) > 4.0 or
                    abs(proximal[i] - proximal_init) > 4.0 or
                    abs(radial_trans[i] - radial_trans_init) > 4.0):
                    criterion = 4
                    angle_limit = ulnar[i]
                    print(f"    Criterion 4 at i={i}, angle={angle_limit:.2f}°")
                    break

            if criterion is None:
                print("No criterion reached")
                angle_limit = np.nan
                criterion = 0

            results.append({
                "Specimen": specimen,
                "Condition": condition,
                "ROM_ulnar_deg": angle_limit,
                "Critere": criterion,
                "File": filename
            })

    except Exception as e:
        print(f"    ❌ Error: {e}")
        continue

# ========== SAVE RESULTS ==========
if results:
    df = pd.DataFrame(results)
    # Sort by specimen then by condition order (optional)
    condition_order = list(CONDITION_MAP.values())
    df['Condition'] = pd.Categorical(df['Condition'], categories=condition_order, ordered=True)
    df = df.sort_values(['Specimen', 'Condition'])
    print("\n --> Summary:")
    print(df.to_string(index=False))
    output_csv = "adduction_ROM_2specimens.csv"
    df.to_csv(output_csv, index=False)
    print(f"\n Table saved to: {output_csv}")
else:
    print("No files processed.")