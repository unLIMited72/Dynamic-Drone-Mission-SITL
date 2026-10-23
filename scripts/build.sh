#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[[ "${1:-}" != --help ]] || { echo 'Usage: build.sh (reuses exact installed dependencies; no runtime launch)'; exit 0; }
unset PYTHONPATH PYTHONHOME
"$ROOT/scripts/install.sh" --check
mkdir -p "$ROOT/.local/logs"
# Generate firmware version from its own pinned upstream checkout, never copy a developer artifact.
(cd "$ROOT/crazyflie-firmware"; "$ROOT/Drone/bin/python" tools/make/versionTemplate.py src/utils/src/version.vtpl version.c)
D="$ROOT/virtual_aideck/runtime/build/ego_firmware"
if [[ ! -d "$D" ]]; then
 "$ROOT/Drone/bin/python" "$ROOT/virtual_aideck/runtime/state_link/build_firmware.py" "$D" 2>&1 | tee "$ROOT/.local/logs/firmware-build.log"
else
 [[ -x "$D/ON/cf2" && -x "$D/OFF/cf2" ]] || { echo 'Incomplete firmware build; preserve failed directory and choose a fresh build location before retry.'; exit 1; }
fi
# Baseline state-link OFF expects this original path; use the same freshly built OFF firmware.
mkdir -p "$ROOT/crazyflie-firmware/sitl_make/build"
cp "$D/OFF/cf2" "$ROOT/crazyflie-firmware/sitl_make/build/cf2"
EGO_STATE_LINK=1 EGO_FRAME_ASSOCIATION=1 EGO_FRAME_SEND=1 RUNTIME_NETWORK_POLL_US=100 \
 bash "$ROOT/virtual_aideck/runtime/launcher/sdk.sh" build 1 3600000000 2>&1 | tee "$ROOT/.local/logs/gap8-build.log"
echo 'BUILD COMPLETE'
