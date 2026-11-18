#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if ! python3 -c 'import shapely, pyproj' >/dev/null 2>&1; then
    python3 -m pip install --prefer-binary -r requirements-core.txt
fi
exec python3 launch_app.py
