#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
source third_party/gap_sdk_venv/bin/activate
export GAP_RISCV_GCC_TOOLCHAIN="$ROOT/third_party/gap_riscv_toolchain"
export PATH="$GAP_RISCV_GCC_TOOLCHAIN/bin:$PATH"
source third_party/gap_sdk/configs/ai_deck.sh
RUNTIME="$ROOT/virtual_aideck/runtime"
mkdir -p "$RUNTIME/build"
if [[ "${EGO_STATE_LINK:-0}" == 1 ]]; then
  python "$RUNTIME/state_link/virtual_uart/model_path.py" "$GVSOC_PATH" "$RUNTIME/build/vp_models"
  export GVSOC_PATH="$RUNTIME/build/vp_models"
fi
if [[ "$1" == build ]]; then
  inc="$ROOT/third_party/gap_sdk/install/workstation/include"
  # Reuse models only when sources, builder and public DPI header match.
  stamp=$(sha256sum "$RUNTIME"/camera_input/*.cpp "$RUNTIME"/camera_input/*.hpp "$RUNTIME"/esp32/*.cpp "$RUNTIME"/esp32/*.hpp "$RUNTIME/launcher/quiet_trace.cpp" "$0" "$inc/dpi/models.hpp" | sha256sum)
  if [[ ! -f "$RUNTIME/build/models.sha256" || "$(< "$RUNTIME/build/models.sha256")" != "$stamp" || ! -f "$RUNTIME/build/live_camera.so" || ! -f "$RUNTIME/build/cpx_spi_bridge.so" || ! -f "$RUNTIME/build/quiet_trace.so" ]]; then
  g++ -std=c++11 -O2 -g -shared -fPIC -I"$inc" "$RUNTIME/camera_input/live_camera.cpp" -lcrypto -o "$RUNTIME/build/live_camera.so"
  g++ -std=c++11 -O2 -g -shared -fPIC -I"$inc" "$RUNTIME/esp32/cpx_spi_bridge.cpp" "$RUNTIME/esp32/cpx_protocol.cpp" -o "$RUNTIME/build/cpx_spi_bridge.so"
  g++ -std=c++11 -O2 -g -shared -fPIC -I"$inc" "$RUNTIME/launcher/quiet_trace.cpp" -o "$RUNTIME/build/quiet_trace.so"
  printf '%s\n' "$stamp" > "$RUNTIME/build/models.sha256"
  fi
  if [[ "${EGO_STATE_LINK:-0}" == 1 ]]; then
    g++ -std=c++11 -O2 -g -shared -fPIC -I"$inc" "$RUNTIME/state_link/virtual_uart/state_uart.cpp" -o "$RUNTIME/build/vp_models/state_uart.so"
  fi
  make -C "$RUNTIME/gap8" clean all platform=gvsoc NETWORK_POLL_US="${RUNTIME_NETWORK_POLL_US:-10}" FRAME_ASSOCIATION="${EGO_FRAME_ASSOCIATION:-0}" FRAME_STATE_SEND="${EGO_FRAME_SEND:-0}" STATE_LINK="${EGO_STATE_LINK:-0}" STATE_FAULTS="${EGO_FAULTS:-0}" STATE_DIAGNOSTICS="${EGO_STATE_DIAGNOSTICS:-0}" SESSION_ID="$2" SESSION_US="${3:-3600000000}"
else
  export LD_PRELOAD="$RUNTIME/build/quiet_trace.so"
  exec stdbuf -oL make -C "$RUNTIME/gap8" run platform=gvsoc NETWORK_POLL_US="${RUNTIME_NETWORK_POLL_US:-10}" FRAME_ASSOCIATION="${EGO_FRAME_ASSOCIATION:-0}" FRAME_STATE_SEND="${EGO_FRAME_SEND:-0}" STATE_LINK="${EGO_STATE_LINK:-0}" STATE_FAULTS="${EGO_FAULTS:-0}" STATE_DIAGNOSTICS="${EGO_STATE_DIAGNOSTICS:-0}" SESSION_ID="$2" SESSION_US="${3:-3600000000}"
fi
