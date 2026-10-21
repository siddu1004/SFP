#!/usr/bin/env sh
# Install SFP skills. Examples:
#   ./install.sh                          starter set into every tool found
#   ./install.sh --profile everything
#   ./install.sh list
set -e
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
case "${1:-}" in
  ""|-*) set -- install "$@" ;;
esac
exec "$PY" scripts/install.py "$@"
