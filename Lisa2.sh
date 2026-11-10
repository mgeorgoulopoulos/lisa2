#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$APP_DIR"
if [ -x "$APP_DIR/.venv/bin/python" ]; then
    exec "$APP_DIR/.venv/bin/python" "$APP_DIR/scripts/run_source.py" "$@"
fi
if [ -n "${LISA2_PYTHON:-}" ]; then
    exec "$LISA2_PYTHON" "$APP_DIR/scripts/run_source.py" "$@"
fi
for candidate in python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert sys.version_info[:2] == (3,12)' >/dev/null 2>&1; then
        exec "$candidate" "$APP_DIR/scripts/run_source.py" "$@"
    fi
done
echo 'Lisa2 requires Python 3.12 with venv and Tk support.' >&2
echo 'Install your distribution’s matching Python packages, then run bash Lisa2.sh again.' >&2
exit 1
