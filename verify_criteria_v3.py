"""
verify_criteria_v3.py

Load a single TDMS file and plot translations, torques, and angle,
marking the first criterion according to config.json.
"""

import os
import json
import numpy as np
import matplotlib.pyplot as plt
from nptdms import TdmsFile

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

FILE_PATH = input("Enter path to .tdms file: ").strip()
# Remove surrounding quotes if present
if FILE_PATH.startswith(("'", '"')) and FILE_PATH.endswith(("'", '"')):
    FILE_PATH = FILE_PATH[1:-1]

MOVEMENT_CODE = input("Enter movement code (e.g., ADD_dislocation): ").strip()

# Check if file exists
if not os.path.exists(FILE_PATH):
    print(f"Error: File not found: {FILE_PATH}")
    exit(1)

TH = config["thresholds"]
GROUPS = config["tdms_groups"]
CH = config["tdms_channels"]

DROP_TRANSLATION = TH["drop_translation"]
DROP_TORQUE_RATE = TH["drop_torque_rate"]
START_IDX = TH["start_idx"]
TRANS_LIMIT = TH["translation_limit_mm"]
TORQUE_LIMIT = TH["torque_limit_nm"]

def resultant_torque(r, s, e):
    return np.sqrt(r**2 + s**2 + e**2)

with TdmsFile.open(FILE_PATH) as tdms:
    # Time
    try:
        grp_time = tdms[GROUPS["time"]]
        time = grp_time[CH["time"]].read_data()
        time = np.array(time)
        has_time = True
        dt = np.diff(time)
        dt = np.where(dt == 0, 1e-9, dt)
    except:
        has_time = False
        time = None

    # Kinematics and load groups
    grp_kin = tdms[GROUPS["kinematics"]]
    grp_load = tdms[GROUPS["load"]]

    # Read channels
    try:
        ulnar = np.array(grp_kin[CH["ulnar"]].read_data())
        flexion = np.array(grp_kin[CH["flexion"]].read_data())
        volar = np.array(grp_kin[CH["volar"]].read_data())
        proximal = np.array(grp_kin[CH["proximal"]].read_data())
        radial_trans = np.array(grp_kin[CH["radial_trans"]].read_data())
    except KeyError as e:
        print(f"Missing channel: {e}. File may not be an implant trial.")
        exit(1)

    try:
        radial_torque = np.array(grp_load[CH["radial_torque"]].read_data(), dtype=float)
        supination_torque = np.array(grp_load[CH["supination_torque"]].read_data(), dtype=float)
        extension_torque = np.array(grp_load[CH["extension_torque"]].read_data(), dtype=float)
    except (ValueError, TypeError, KeyError) as e:
        print(f"Torque data issue: {e}")
        exit(1)

    torque_res = resultant_torque(radial_torque, supination_torque, extension_torque)

    n_init = 10
    volar_init = np.mean(volar[:n_init])
    proximal_init = np.mean(proximal[:n_init])
    radial_trans_init = np.mean(radial_trans[:n_init])

    # Choose angle based on movement code
    if "ADD" in MOVEMENT_CODE or "ABD" in MOVEMENT_CODE:
        angle = ulnar
        angle_label = "Ulnar Rotation (adduction/abduction)"
    else:
        angle = flexion
        angle_label = "Flexion Angle (flexion/extension)"

    criterion_idx = None
    criterion_num = None

    for i in range(START_IDX, len(angle)):
        if has_time:
            rate_r = (radial_torque[i] - radial_torque[i-1]) / dt[i-1]
            rate_s = (supination_torque[i] - supination_torque[i-1]) / dt[i-1]
            rate_e = (extension_torque[i] - extension_torque[i-1]) / dt[i-1]
            if (rate_r < DROP_TORQUE_RATE or rate_s < DROP_TORQUE_RATE or rate_e < DROP_TORQUE_RATE):
                criterion_idx = i
                criterion_num = 1
                break

        if (abs(volar[i] - volar_init) > TRANS_LIMIT or
            abs(proximal[i] - proximal_init) > TRANS_LIMIT or
            abs(radial_trans[i] - radial_trans_init) > TRANS_LIMIT):
            criterion_idx = i
            criterion_num = 2
            break

        if torque_res[i] >= TORQUE_LIMIT:
            criterion_idx = i
            criterion_num = 3
            break

        if (volar[i] - volar[i-1] < DROP_TRANSLATION or
            proximal[i] - proximal[i-1] < DROP_TRANSLATION or
            radial_trans[i] - radial_trans[i-1] < DROP_TRANSLATION):
            criterion_idx = i
            criterion_num = 4
            break

    if criterion_idx is None:
        print("No criterion triggered.")
    else:
        time_val = time[criterion_idx] if has_time else criterion_idx
        print(f"Criterion {criterion_num} at index {criterion_idx}, time = {time_val:.3f}s, angle = {angle[criterion_idx]:.2f}°")

    # Plot
    x = time if has_time else np.arange(len(angle))
    xlabel = "Time (s)" if has_time else "Sample Index"

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    axes[0].plot(x, volar, label='Volar Translation')
    axes[0].plot(x, proximal, label='Proximal Translation')
    axes[0].plot(x, radial_trans, label='Radial Translation')
    axes[0].set_ylabel('Translation (mm)')
    axes[0].legend()
    axes[0].grid(True)

    axes[1].plot(x, radial_torque, label='Radial Rotation Torque')
    axes[1].plot(x, supination_torque, label='Supination Torque')
    axes[1].plot(x, extension_torque, label='Extension Torque')
    axes[1].plot(x, torque_res, '--', label='Resultant Torque')
    axes[1].axhline(y=TORQUE_LIMIT, color='k', linestyle=':', label=f'{TORQUE_LIMIT} Nm threshold')
    axes[1].set_ylabel('Torque (Nm)')
    axes[1].legend()
    axes[1].grid(True)

    axes[2].plot(x, angle, label=angle_label)
    axes[2].set_ylabel('Angle (deg)')
    axes[2].set_xlabel(xlabel)
    axes[2].legend()
    axes[2].grid(True)

    if criterion_idx is not None:
        for ax in axes:
            ax.axvline(x=x[criterion_idx], color='red', linestyle='--', linewidth=2)
            ax.text(x[criterion_idx], ax.get_ylim()[1]*0.95, f'C{criterion_num}',
                    color='red', ha='center', va='top', fontsize=12, fontweight='bold')

    plt.suptitle(os.path.basename(FILE_PATH))
    plt.tight_layout()
    plt.savefig('verification_plot.png', dpi=150)
    plt.show()