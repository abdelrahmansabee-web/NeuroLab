#!/usr/bin/env bash
# Restore the live Hugging Face Space working tree from this snapshot.
# Usage:
#   ./restore_hf_space.sh /path/to/hf_repo
# The target must be a git checkout of
#   https://huggingface.co/spaces/AbdelrahmanSabee/neurolab.git
set -euo pipefail

SNAP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SNAP_DIR/hf_space"
DEST="${1:-}"

if [ -z "$DEST" ]; then
  echo "Usage: $0 /path/to/hf_repo" >&2
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
# Copy snapshot files over the checkout. Do not delete dest .git.
tar -C "$SRC" -cf - . | tar -C "$DEST" -xf -

echo "Done. Review, commit, and push from $DEST"
echo "  git -C \"$DEST\" status"
echo "  git -C \"$DEST\" add -A && git -C \"$DEST\" commit -m 'Restore from REFERENCE_SNAPSHOT_v31.75'"
