#!/usr/bin/env sh
# SFP bootstrap for macOS and Linux. Clones (or updates) SFP into ~/.sfp/SFP and runs the installer.
#   curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh
#   curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- --profile frontend-dev --tools cursor
# Set SFP_DIR to use another folder.
set -e
DIR="${SFP_DIR:-$HOME/.sfp/SFP}"
command -v git >/dev/null 2>&1 || { echo "git is required: https://git-scm.com/downloads" >&2; exit 1; }
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull -q --ff-only
else
  mkdir -p "$(dirname "$DIR")"
  git clone -q --depth 1 https://github.com/siddu1004/SFP.git "$DIR"
fi
exec sh "$DIR/install.sh" "$@"
