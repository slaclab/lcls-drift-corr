# Drift Correction

Python-based ATM feedback for drift correction in laser timing (LCLS-II cRIXS/qRIXS). Includes a PyDM GUI and parameter configs.

## Files

| File                        | Description                       |
|-----------------------------|-----------------------------------|
| `drift_correction_main.py`  | Main feedback script              |
| `drift_correction_gui.py`   | PyDM GUI                          |
| `drift_correction_gui_qrixs.py`   | PyDM GUI (qRIXS)                          |
| `crixs_atm_fb.json`         | cRIXS parameters                  |
| `qrixs_atm_fb.json`         | qRIXS parameters                  |

## Requirements

- Python 3.7+
- PyDM, qtpy, psutil, numpy, psp
- EPICS PV access

## Usage

To launch the GUI:

```
ssh las-console
cd /cds/group/laser/timing/lcls-drift-corr/
source /cds/group/pcds/pyps/conda/pcds_conda
python drift_correction_gui.py &
```

## Config

Edit the JSON files to change PVs and defaults as needed.

## Previous History

Earlier commits are at:  
[https://github.com/slaclab/femto-timing/tree/lcls2-drift-correction](https://github.com/slaclab/femto-timing/tree/lcls2-drift-correction)
