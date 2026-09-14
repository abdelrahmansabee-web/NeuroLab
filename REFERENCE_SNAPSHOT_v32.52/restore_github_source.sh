#!/usr/bin/env bash
# Restore NeuroLab GitHub / local source from this snapshot.
# Usage:
#   ./restore_github_source.sh /path/to/NeuroLab
# The target must be a git checkout of
#   https://github.com/abdelrahmansabee-web/NeuroLab
set -euo pipefail

SNAP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SNAP_DIR/github_source"
DEST="${1:-}"

if [ -z "$DEST" ]; then
  echo "Usage: $0 /path/to/NeuroLab" >&2
  exit 1
fi
if [ ! -d "$SRC" ]; then
  echo "Missing snapshot source: $SRC" >&2
  exit 1
fi
if [ ! -d "$DEST" ]; then
  echo "Destination does not exist: $DEST" >&2
  exit 1
fi
if [ ! -d "$DEST/.git" ]; then
  echo "Destination is not a git checkout: $DEST" >&2
  exit 1
fi

echo "Restoring $SRC -> $DEST (keeping destination .git)"
tar -C "$SRC" -cf - . | tar -C "$DEST" -xf -

echo "Done. Review from $DEST"
echo "  git -C \"$DEST\" status"
echo "Rebuild frontend with: cd frontend && npm ci && npm run build"
