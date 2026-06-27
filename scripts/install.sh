#!/usr/bin/env bash
# Install Hermes Iris (KakaoTalk) platform plugin from a git checkout.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PLUGIN_SRC="$REPO_ROOT/plugins/platforms/iris"
PLUGIN_DEST="$HERMES_HOME/plugins/platforms/iris"

echo "=== Hermes Iris plugin install ==="
echo "Source: $PLUGIN_SRC"
echo "Target: $PLUGIN_DEST"

if [[ ! -f "$PLUGIN_SRC/plugin.yaml" ]]; then
  echo "error: plugin.yaml not found at $PLUGIN_SRC" >&2
  exit 1
fi

if ! command -v hermes >/dev/null 2>&1; then
  echo "Hermes CLI not found. Install first, e.g.:"
  echo "  pip install hermes-agent"
  exit 1
fi

mkdir -p "$HERMES_HOME/plugins/platforms"
ln -sfn "$PLUGIN_SRC" "$PLUGIN_DEST"
echo "Linked plugin -> $PLUGIN_DEST"

if python3 -c "import websockets" 2>/dev/null; then
  echo "websockets: OK"
else
  echo "Installing websockets..."
  pip install websockets
fi

# Enable plugin in config (platforms/iris symlink layout)
python3 - <<'PY'
import os
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML not found; enable plugin manually: hermes plugins enable platforms/iris")
    raise SystemExit(0)

home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
cfg_path = home / "config.yaml"
cfg = {}
if cfg_path.exists():
    cfg = yaml.safe_load(cfg_path.read_text()) or {}

plugins = cfg.setdefault("plugins", {})
enabled = plugins.setdefault("enabled", [])
if not isinstance(enabled, list):
    enabled = []
key = "platforms/iris"
if key not in enabled:
    enabled.append(key)
    plugins["enabled"] = enabled
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False))
    print(f"Added '{key}' to plugins.enabled in {cfg_path}")
else:
    print(f"'{key}' already in plugins.enabled")
PY

echo ""
echo "Next steps:"
echo "  1. hermes setup iris          # Iris host/port, allowed rooms"
echo "  2. hermes gateway run         # start gateway"
echo ""
echo "Example config: $REPO_ROOT/config/iris.example.yaml"