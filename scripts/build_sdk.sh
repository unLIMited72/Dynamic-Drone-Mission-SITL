#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
unset PYTHONPATH PYTHONHOME GAP_RISCV_GCC_TOOLCHAIN_BASE
source "$ROOT/third_party/gap_sdk_venv/bin/activate"
export GAP_RISCV_GCC_TOOLCHAIN="$ROOT/third_party/gap_riscv_toolchain"
source "$ROOT/third_party/gap_sdk/configs/ai_deck.sh"
# Native simulation needs no physical USB/FTDI flasher. Avoid its implicit git:// download.
cmake -S "$ROOT/third_party/gap_sdk/tools/pulp_tools" -B "$ROOT/third_party/gap_sdk/build" \
 -DWithFTDI=OFF -DWithFlasher=OFF -DCMAKE_INSTALL_PREFIX="$INSTALL_DIR" -DTARGET_INSTALL_DIR="$TARGET_INSTALL_DIR"
# SDK 3.8.1 header export ordering is unsafe with top-level parallel make.
make -C "$ROOT/third_party/gap_sdk" -j1 gvsoc EXTRA_CMAKE_ARGS="-DWithFTDI=OFF -DWithFlasher=OFF"
