
# CAN Reader

A robust CAN log parsing and analysis tool designed for real-world machine data.

This tool reads CAN logs, cleans byte data (d0–d7), performs statistical analysis on CAN IDs,
and generates plots for byte-level and signal-level exploration.

It is designed to handle messy datasets commonly found in machine logs, such as:

- missing bytes
- NaN values
- mixed hex formats
- inconsistent CAN ID formats

The goal of this project is to help engineers explore CAN datasets and discover potential signals
from unknown protocols.

---

# Features

- Robust CAN log parsing
- Handles NaN and malformed hex values
- Automatic byte conversion (d0–d7 → integers)
- CAN ID frequency statistics
- Period timing analysis
- Byte-level plotting
- Adjacent byte signal exploration
- Exported CSV summaries
- Automatic plot generation

---

# Installation

Clone the repository:

git clone https://github.com/YOURNAME/can-reader.git
cd can-reader

Install dependencies:

pip install -r requirements.txt

---

# Usage

python can_reader_refactored.py --input your_can_log.asc --outdir output --can-id 586 --limit 300

Parameters:

--input   Path to CAN log file  
--outdir  Output directory  
--can-id  CAN ID to analyze  
--limit   Number of samples used for plotting

---

# Output

The script generates:

output/
├── canid_summary.csv
├── run_report.txt
├── plots_bytes/
└── plots_signals/

---

# Input File Assumptions

The script expects the input file to contain at least 14 columns, mapped internally as:

timestamp
channel
direction
can_id
dlc
d0
d1
d2
d3
d4
d5
d6
d7

Extra columns will be ignored.

---

# Contributing

Contributions are welcome.

Useful contributions include:

- CAN logs from different machines
- bug reports
- improvements to parsing robustness
- signal discovery notes

If submitting a dataset, please include:

- machine brand
- machine model
- logger type
- CAN bus source (if known)
- operating scenario

Only upload data you are authorized to share.

---

# Disclaimer

This project is intended for engineering analysis and interoperability research on CAN data
that users are authorized to access.
