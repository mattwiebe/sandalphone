#!/usr/bin/env bash
set -euo pipefail

export UV_CACHE_DIR=/opt/levi-runtime-cloud/.uv-cache
mkdir -p "$UV_CACHE_DIR"

cd /opt/levi-runtime-cloud
exec /usr/local/bin/uv run --frozen uvicorn runtime_cloud_service.app:app --host 0.0.0.0 --port 8787
