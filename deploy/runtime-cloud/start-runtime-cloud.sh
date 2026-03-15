#!/usr/bin/env bash
set -euo pipefail

export UV_CACHE_DIR=/opt/levi/.uv-cache
mkdir -p "$UV_CACHE_DIR"

if [[ -n "${NLTK_DATA:-}" ]]; then
  mkdir -p "$NLTK_DATA"
fi

cd /opt/levi/runtime-cloud
exec /usr/local/bin/uv run --frozen uvicorn runtime_cloud_service.app:app --host 0.0.0.0 --port 8787
