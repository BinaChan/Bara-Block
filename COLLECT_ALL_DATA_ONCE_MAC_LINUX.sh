#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m pip install -r requirements-data.txt
python3 COLLECT_ALL_DATA_ONCE.py
python3 era5_open_meteo.py --date 2024-01-01 || echo "ERA5-Land pending: provider unavailable."
python3 export_structured.py
