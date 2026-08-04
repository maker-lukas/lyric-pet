#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
export LYRICS_DELAY_MS=0
export DISPLAY_SUPPORTS_ICONS=1
python_bin=python
if [[ -x .venv/bin/python ]]; then
  python_bin=.venv/bin/python
fi
exec "$python_bin" device_host_linux.py
