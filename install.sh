#!/usr/bin/env sh
# Install the combined skills. Run `./install.sh list` to see bundles and tools.
set -e
cd "$(dirname "$0")"
if [ $# -eq 0 ]; then set -- install; fi
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
exec "$PY" scripts/install.py "$@"
