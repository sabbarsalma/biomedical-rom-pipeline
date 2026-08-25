# User Guide: CMC Thumb Analysis Pipeline

Biomechanical Analysis, Python, TDMS

## 1. Prerequisites

- **Operating System:** macOS (tested), Linux, Windows (path adjustments required)
- **Python:** version 3.9 or higher
- **Virtual environment:** venv (recommended)
- **Python packages:** `nptdms`, `pandas`, `numpy`, `matplotlib`

## 2. Installation

1. Download or clone the project files into a folder (e.g. `CMC_python`).
2. Open a terminal in that folder.
3. Create the virtual environment:

```bash
python3 -m venv venv
```

4. Activate the environment:

```bash
source venv/bin/activate      # macOS / Linux
.\venv\Scripts\activate       # Windows
```

5. Install the dependencies:

```bash
pip install nptdms pandas numpy matplotlib
```

## 3. File Structure

| File | Role |
|---|---|
| `config.json` | Configuration file (paths, thresholds, specimen list, channel names) |
| `build_full_table_v3.py` | Main script for generating ROM tables |
| `verify_criteria_v3.py` | Visual verification script for a single file |
| `generate_all_tables.py` | (Optional) generates pivot tables and global average |
| Data folder | simVITRO directory tree, each specimen in its own sub-folder with a Data sub-directory |

## 4. Configuring config.json

| Field | Description | Example |
|---|---|---|
| `root_dir` | Absolute path to the parent folder containing all specimen sub-folders. | `"/path/to/All_Specimens"` |
| `specimens` | List of specimen folder names to analyse. | `["3231_L", "3231_R", ...]` |
| `file_type` | File type: processed or raw. | `"processed"` |
| `movement_codes` | Mapping between filename code and movement name (pre-defined). | (pre-defined) |
| `condition_map` | Mapping between condition code and human-readable name (pre-defined). | (pre-defined) |

### Threshold Parameters

| Parameter | Description | Recommended value |
|---|---|---|
| `drop_translation` | Translation drop threshold (mm), criterion 4. | -0.1 (more sensitive) |
| `drop_torque_rate` | Torque derivative threshold (Nm/s), criterion 1. | -5.0 (balanced) |
| `start_idx` | Start index for analysis (skips initial noise). | 1000 |
| `translation_limit_mm` | Translation threshold > 4 mm, criterion 2. | 4.0 |
| `torque_limit_nm` | Resultant torque threshold, criterion 3. | 1.0 |

> Tip: thresholds can be adjusted without modifying the code. Simply update `config.json` and re-run the scripts.

## 5. Running the Main Script

```bash
python build_full_table_v3.py
```

This script:

- Iterates over all specimens listed in `config.json`.
- Reads each `*_processed.tdms` file for the 8 movements.
- Applies criteria in order: 1 = torque rate, 2 = translation > 4 mm, 3 = resultant torque, 4 = translation drop.
- Outputs `full_ROM_all_specimens.csv` (global table) and `ROM_<specimen>.csv` (per specimen).

Runtime: execution may take several minutes depending on the number of files. Progress messages are displayed throughout.

## 6. Visual Verification of a File

```bash
python verify_criteria_v3.py
```

The script prompts interactively for:

- **File path (.tdms):** drag and drop the file into the terminal.
- **Movement code** (e.g. `ADD_dislocation`).

The script displays the detected criterion, time, and angle, then opens a graphical window showing three curves (translations, torques, angle) with a vertical red line at the trigger point. The figure is also saved as `verification_plot.png`.

## 7. Generating Formatted Tables (Optional)

```bash
python generate_all_tables.py
```

This script reads the `ROM_<specimen>.csv` files and produces:

- For each specimen: a pivot table `ROM_Table_<specimen>.csv` (rows = conditions, columns = movements, cells = ROM or mean ± SD if multiple trials).
- A global average table `ROM_Table_Average.csv` (mean ± SD across all specimens).

These tables are ready to be included in a report or analysed in Excel.

## 8. Troubleshooting

| Error / symptom | Probable cause | Solution |
|---|---|---|
| `FileNotFoundError` | Incorrect path in `config.json` or user input | Verify that `root_dir` exists and that specimen sub-folders are present inside it. |
| `KeyError: 'Ulnar Rotation'` | File missing this channel (e.g. native specimen) | The script skips these files automatically. Ensure you are analysing implant trials (containing `BP` in the filename). |
| No criterion triggered | Thresholds are too strict | Decrease the absolute value of `drop_torque_rate` (e.g. -3.0) or `drop_translation` (e.g. -0.05). |
| `NameError: name 'os' is not defined` | Missing import in `verify_criteria_v3.py` | Add `import os` at the top of the script (already fixed in the provided version). |
| Execution too slow | Too many files to process | Reduce the specimen list in `config.json` to test on a smaller sample first. |

## 9. Adding a New Specimen

1. Place the new specimen folder inside the `root_dir` directory.
2. Add its name exactly as the folder name to the `specimens` list in `config.json`.
3. Re-run `build_full_table_v3.py`. The new specimen will be included automatically.

## 10. Advanced Customisation

- **Change criterion order:** edit the loop `for i in range(START_IDX, len(ulnar))` in `build_full_table_v3.py` to swap the if blocks.
- **Add a new movement:** extend `MOVEMENTS` and `MOVEMENT_DEFS` in the main script.
- **Use raw files:** set `"file_type": "raw"` in `config.json` (note: no resampling is applied).
