#!/usr/bin/env bash
# Launch SDLC Agents fully offline on the local device.
set -euo pipefail

# Disable Streamlit telemetry (no external communication).
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Optional: relocate all app state (config + artifacts) to an encrypted volume.
# export SDLC_AGENTS_HOME="/secure/volume/.sdlc_agents"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Bind to localhost so nothing is exposed on the network by default.
exec streamlit run app.py \
  --server.address=127.0.0.1 \
  --server.port="${SDLC_PORT:-8501}" \
  --browser.gatherUsageStats=false
