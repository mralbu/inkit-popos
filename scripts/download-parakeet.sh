#!/usr/bin/env bash
# Download a sherpa-onnx Parakeet (NeMo transducer) model for local STT.
#
# Usage: scripts/download-parakeet.sh [MODEL] [DEST_DIR]
#   MODEL     model archive name (default: sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8)
#   DEST_DIR  where to place encoder/decoder/joiner.onnx + tokens.txt
#             (default: ~/.local/share/inkit-popos/models/parakeet)
#
# Models are published on the sherpa-onnx 'asr-models' GitHub release:
#   https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models
set -euo pipefail

MODEL="${1:-sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8}"
DEST="${2:-$HOME/.local/share/inkit-popos/models/parakeet}"
BASE="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models"
URL="$BASE/${MODEL}.tar.bz2"

echo "Model:       $MODEL"
echo "Destination: $DEST"
echo "URL:         $URL"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "Downloading…"
curl -L --fail -o "$tmp/model.tar.bz2" "$URL"

echo "Extracting…"
tar -xjf "$tmp/model.tar.bz2" -C "$tmp"

mkdir -p "$DEST"
# Flatten the single top-level directory from the archive into DEST.
src="$(find "$tmp" -mindepth 1 -maxdepth 1 -type d | head -n1)"
cp -v "$src"/*.onnx "$DEST"/ 2>/dev/null || true
cp -v "$src"/tokens.txt "$DEST"/ 2>/dev/null || true

echo
echo "Done. Set parakeet.model_dir = \"$DEST\" in your config (it's the default)."
echo "Verify with: inkit-popos doctor"
