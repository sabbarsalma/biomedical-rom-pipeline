"""
build_full_table_v3.py

Process all processed TDMS files for all 8 movements using a configuration file.
All thresholds and specimen lists are read from config.json.
Outputs CSV tables per specimen and a global table.
"""

import os
import json
import numpy as np
import pandas as pd
from nptdms import TdmsFile

# ========== LOAD CONFIGURATION ==========
with open("config.json", "r") as f:
    config = json.load(f)

ROOT_DIR = config["root_dir"]
SPECIMENS = config["specimens"]
FILE_TYPE = config["file_type"]
MOVEMENTS = config["movement_codes"]
CONDITION_MAP = config["condition_map"]
THRESHOLDS = config["thresholds"]
GROUPS = config["tdms_groups"]
CHANNELS = config["tdms_channels"]

DROP_TRANSLATION = THRESHOLDS["drop_translation"]
DROP_TORQUE_RATE = THRESHOLDS["drop_torque_rate"]
START_IDX = THRESHOLDS["start_idx"]
TRANS_LIMIT = THRESHOLDS["translation_limit_mm"]
TORQUE_LIMIT = THRESHOLDS["torque_limit_nm"]

# ========== HELPER FUNCTIONS ==========
def resultant_torque(r, s, e):
    return np.sqrt(r**2 + s**2 + e**2)

def get_angle_value(flexion, ulnar, mov_def):
    if mov_def.get("combined"):
        val1 = flexion
        val2 = ulnar
        if "primary_sign" in mov_def:
            val1 = mov_def["primary_sign"] * val1
        return val1 if abs(val1) >= abs(val2) else val2
    else:
        if mov_def.get("sign") == -1:
            return -flexion if "Flexion" in mov_def.get("name", "") else -ulnar
        return flexion if "Flexion" in mov_def.get("name", "") else ulnar

# Movement definitions (with sign/combined info)
MOVEMENT_DEFS = {
    "FE_dislocation": {"name": "Flexion", "primary": "flexion", "sign": 1},
    "ABD_dislocation": {"name": "Abduction", "primary": "ulnar", "sign": -1},
    "ADD_dislocation": {"name": "Adduction", "primary": "ulnar", "sign": 1},
    "Ext_dislocation": {"name": "Extension", "primary": "flexion", "sign": -1},
    "ABD_Flex_dislocation": {"name": "Flexion-Abduction", "combined": True, "primary": "flexion", "secondary": "ulnar", "primary_sign": 1},
    "ADD_Flex_dislocation": {"name": "Flexion-Adduction", "combined": True, "primary": "flexion", "secondary": "ulnar", "primary_sign": 1},
    "ABD_Ext_dislocation": {"name": "Extension-Abduction", "combined": True, "primary": "flexion", "secondary": "ulnar", "primary_sign": -1},
    "ADD_Ext_dislocation": {"name": "Extension-Adduction", "combined": True, "primary": "flexion", "secondary": "ulnar", "primary_sign": -1}
}

def extract_condition_code(filename):
    for code in CONDITION_MAP:
        if code in filename:
            return code
    return "Unknown"

def extract_specimen_from_path(filepath):
    try:
        return os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(filepath))))
    except:
        return "Unknown"

# ========== PROCESS ALL SPECIMENS ==========
all_results = []

for specimen in SPECIMENS:
    specimen_folder = os.path.join(ROOT_DIR, specimen)
    if not os.path.isdir(specimen_folder):
        print(f"Warning: {specimen_folder} not found, skipping.")
        continue

    print(f"\nProcessing specimen: {specimen}")
    for root, dirs, files in os.walk(specimen_folder):
        if os.path.basename(root) != "Data":
            continue
        for mov_code, mov_name in MOVEMENTS.items():
            matching = [f for f in files if mov_code in f and FILE_TYPE in f and f.endswith('.tdms')]
            if not matching:
                continue
            filename = matching[0]
            filepath = os.path.join(root, filename)
            code = extract_condition_code(filename)
            condition = CONDITION_MAP.get(code, code)
            mov_def = MOVEMENT_DEFS[mov_code]

            try:
                with TdmsFile.open(filepath) as tdms:
                    # Time (optional)
                    try:
                        grp_time = tdms[GROUPS["time"]]
                        time = grp_time[CHANNELS["time"]].read_data()
                        time = np.array(time)
                        has_time = True
                        dt = np.diff(time)
                        dt = np.where(dt == 0, 1e-9, dt)
                    except:
                        has_time = False
                        dt = None

                    # Kinematics group
                    try:
                        grp_kin = tdms[GROUPS["kinematics"]]
                    except KeyError:
                        print(f"      Skipping {filename}: no kinematics group")
                        continue

                    # Load group
                    try:
                        grp_load = tdms[GROUPS["load"]]
                    except KeyError:
                        print(f"      Skipping {filename}: no load group")
                        continue

                    # Read angle and translation channels (required)
                    try:
                        ulnar = np.array(grp_kin[CHANNELS["ulnar"]].read_data())
                        flexion = np.array(grp_kin[CHANNELS["flexion"]].read_data())
                        volar = np.array(grp_kin[CHANNELS["volar"]].read_data())
                        proximal = np.array(grp_kin[CHANNELS["proximal"]].read_data())
                        radial_trans = np.array(grp_kin[CHANNELS["radial_trans"]].read_data())
                    except KeyError as e:
                        print(f"      Skipping {filename}: missing channel {e}")
                        continue

                    # Read torque channels and force numeric conversion
                    try:
                        radial_torque = np.array(grp_load[CHANNELS["radial_torque"]].read_data(), dtype=float)
                        supination_torque = np.array(grp_load[CHANNELS["supination_torque"]].read_data(), dtype=float)
                        extension_torque = np.array(grp_load[CHANNELS["extension_torque"]].read_data(), dtype=float)
                    except (ValueError, TypeError, KeyError) as e:
                        print(f"      Skipping {filename}: torque data issue ({e})")
                        continue

                    # Resultant torque
                    torque_res = resultant_torque(radial_torque, supination_torque, extension_torque)

                    # Initial translations for criterion 2
                    n_init = 10
                    volar_init = np.mean(volar[:n_init])
                    proximal_init = np.mean(proximal[:n_init])
                    radial_trans_init = np.mean(radial_trans[:n_init])

                    # Detect first criterion
                    criterion = None
                    idx_limit = None

                    for i in range(START_IDX, len(ulnar)):
                        # Priority 1: torque rate drop
                        if has_time:
                            rate_r = (radial_torque[i] - radial_torque[i-1]) / dt[i-1]
                            rate_s = (supination_torque[i] - supination_torque[i-1]) / dt[i-1]
                            rate_e = (extension_torque[i] - extension_torque[i-1]) / dt[i-1]
                            if (rate_r < DROP_TORQUE_RATE or rate_s < DROP_TORQUE_RATE or rate_e < DROP_TORQUE_RATE):
                                criterion = 1
                                idx_limit = i
                                break

                        # Priority 2: translation > 4 mm
                        if (abs(volar[i] - volar_init) > TRANS_LIMIT or
                            abs(proximal[i] - proximal_init) > TRANS_LIMIT or
                            abs(radial_trans[i] - radial_trans_init) > TRANS_LIMIT):
                            criterion = 2
                            idx_limit = i
                            break

                        # Priority 3: resultant torque >= 1 Nm
                        if torque_res[i] >= TORQUE_LIMIT:
                            criterion = 3
                            idx_limit = i
                            break

                        # Priority 4: sudden translation drop
                        if (volar[i] - volar[i-1] < DROP_TRANSLATION or
                            proximal[i] - proximal[i-1] < DROP_TRANSLATION or
                            radial_trans[i] - radial_trans[i-1] < DROP_TRANSLATION):
                            criterion = 4
                            idx_limit = i
                            break

                    if criterion is None:
                        rom = np.nan
                        criterion = 0
                    else:
                        f_val = flexion[idx_limit]
                        u_val = ulnar[idx_limit]
                        if mov_def.get("combined"):
                            val1 = f_val if mov_def["primary"] == "flexion" else u_val
                            val2 = u_val if mov_def["secondary"] == "ulnar" else f_val
                            if "primary_sign" in mov_def:
                                val1 = mov_def["primary_sign"] * val1
                            rom = val1 if abs(val1) >= abs(val2) else val2
                        else:
                            if mov_def["primary"] == "flexion":
                                rom = f_val * mov_def.get("sign", 1)
                            else:
                                rom = u_val * mov_def.get("sign", 1)

                    all_results.append({
                        "Specimen": specimen,
                        "Condition": condition,
                        "Movement": mov_name,
                        "ROM_deg": rom,
                        "Critere": criterion,
                        "File": filename
                    })
            except Exception as e:
                print(f"      Unexpected error with {filename}: {e}")
                continue

# ========== SAVE RESULTS ==========
if all_results:
    df = pd.DataFrame(all_results)
    df = df.sort_values(["Specimen", "Condition", "Movement"])
    df.to_csv("full_ROM_all_specimens.csv", index=False)
    print("\n✅ Global table saved: full_ROM_all_specimens.csv")
    for specimen in df["Specimen"].unique():
        spec_df = df[df["Specimen"] == specimen].copy().drop(columns=["Specimen"])
        spec_df.to_csv(f"ROM_{specimen}.csv", index=False)
        print(f"   Per-specimen table saved: ROM_{specimen}.csv")
else:
    print("No files processed.")